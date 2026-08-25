# ============================================================
# windows_agent/agent/uia_information.py
# ============================================================

from __future__ import annotations

import ctypes
import heapq
import re
from dataclasses import dataclass
from typing import Optional

import comtypes
import comtypes.client


TOP_CANDIDATES = 3

TREE_SCOPE_ELEMENT = 1
TREE_SCOPE_CHILDREN = 2
TREE_SCOPE_DESCENDANTS = 4

WINDOW_CONTROL_TYPE = 50032

# Microsoft UIA PropertyConditionFlags.
IGNORE_CASE = 0x01
MATCH_SUBSTRING = 0x02


@dataclass
class UIAElementInfo:
    """
    Store the UIA properties required by the targeting system.

    Coordinates use the Windows virtual-desktop coordinate system.
    """

    name: Optional[str]
    control_type: Optional[str]
    automation_id: Optional[str]

    bounding_rectangle: Optional[
        tuple[float, float, float, float]
    ]

    is_offscreen: bool

    center: Optional[
        tuple[int, int]
    ]

    center_in_virtual_desktop: bool


@dataclass
class UIACandidate:
    """
    Store one UIA candidate together with its confidence.
    """

    element: UIAElementInfo
    confidence: float


class UIAInformation:
    """
    Fast Windows UI Automation candidate discovery.

    The desktop UIA root is the global source of truth.

    Window discovery:
        Desktop root
        -> direct top-level windows

    Control discovery:
        Foreground application
        -> descendant UIA elements

    UIA Text elements remain valid candidates. Their confidence depends
    on their type and physical/actionable state.
    """

    _CONTROL_TYPE_ALIASES = {
        "window": "Window",
        "windows": "Window",

        "button": "Button",
        "buttons": "Button",

        "checkbox": "CheckBox",
        "check box": "CheckBox",
        "checkboxes": "CheckBox",

        "combobox": "ComboBox",
        "combo box": "ComboBox",

        "edit": "Edit",
        "textbox": "Edit",
        "text box": "Edit",
        "input": "Edit",
        "input field": "Edit",
        "field": "Edit",

        "menu": "Menu",
        "menus": "Menu",

        "menuitem": "MenuItem",
        "menu item": "MenuItem",

        "list": "List",
        "listitem": "ListItem",
        "list item": "ListItem",

        "tree": "Tree",
        "treeitem": "TreeItem",
        "tree item": "TreeItem",

        "tab": "TabItem",
        "tabitem": "TabItem",
        "tab item": "TabItem",

        "link": "Hyperlink",
        "hyperlink": "Hyperlink",

        "image": "Image",
        "icon": "Image",

        "radiobutton": "RadioButton",
        "radio button": "RadioButton",

        "slider": "Slider",

        "scrollbar": "ScrollBar",
        "scroll bar": "ScrollBar",

        "toolbar": "ToolBar",
        "tool bar": "ToolBar",

        "pane": "Pane",

        "text": "Text",
        "label": "Text",

        "document": "Document",

        "group": "Group",

        "titlebar": "TitleBar",
        "title bar": "TitleBar",
    }

    def __init__(
        self,
    ) -> None:
        """
        Initialize the native UI Automation client.

        The desktop root is obtained once and reused for global
        top-level-window discovery.
        """

        comtypes.CoInitialize()

        self._uia_module = (
            comtypes.client.GetModule(
                "UIAutomationCore.dll"
            )
        )

        self._automation = (
            comtypes.CoCreateInstance(
                self._uia_module.CUIAutomation._reg_clsid_,
                interface=self._uia_module.IUIAutomation,
                clsctx=comtypes.CLSCTX_INPROC_SERVER,
            )
        )

        self._root = (
            self._automation.GetRootElement()
        )

        self._user32 = ctypes.windll.user32

        # ----------------------------------------------------
        # UIA property IDs
        # ----------------------------------------------------

        self._name_property = (
            self._uia_module.UIA_NamePropertyId
        )

        self._automation_id_property = (
            self._uia_module.UIA_AutomationIdPropertyId
        )

        self._control_type_property = (
            self._uia_module.UIA_ControlTypePropertyId
        )

        self._bounding_rectangle_property = (
            self._uia_module.UIA_BoundingRectanglePropertyId
        )

        self._is_offscreen_property = (
            self._uia_module.UIA_IsOffscreenPropertyId
        )

        self._control_view_condition = (
            self._automation.ControlViewCondition
        )

        # ----------------------------------------------------
        # Cache requests
        # ----------------------------------------------------

        self._element_cache = (
            self._create_element_cache()
        )

        self._window_cache = (
            self._create_element_cache()
        )

    # ========================================================
    # CACHE
    # ========================================================

    def _create_element_cache(
        self,
    ):
        """
        Create a UIA cache request containing only the properties
        required for targeting and coordinate validation.
        """

        cache_request = (
            self._automation.CreateCacheRequest()
        )

        cache_request.AddProperty(
            self._name_property
        )

        cache_request.AddProperty(
            self._automation_id_property
        )

        cache_request.AddProperty(
            self._control_type_property
        )

        cache_request.AddProperty(
            self._bounding_rectangle_property
        )

        cache_request.AddProperty(
            self._is_offscreen_property
        )

        return cache_request

    # ========================================================
    # PUBLIC
    # ========================================================

    def element_from_point(
        self,
        x: int,
        y: int,
    ) -> Optional[UIAElementInfo]:
        """
        Return the UIA element at a virtual-desktop coordinate.

        Negative coordinates are valid when they fall inside the
        Windows virtual desktop.
        """

        if not isinstance(
            x,
            int,
        ):
            raise TypeError(
                "x must be an integer."
            )

        if not isinstance(
            y,
            int,
        ):
            raise TypeError(
                "y must be an integer."
            )

        if not self._point_in_virtual_desktop(
            x,
            y,
        ):
            return None

        point = self._uia_module.tagPOINT(
            int(x),
            int(y),
        )

        try:

            element = (
                self._automation.ElementFromPointBuildCache(
                    point,
                    self._element_cache,
                )
            )

        except Exception:

            return None

        return (
            self._extract_cached_element_info(
                element
            )
        )

    def find_candidates(
        self,
        target: str,
        area: Optional[
            tuple[int, int, int, int]
        ] = None,
        max_candidates: int = TOP_CANDIDATES,
    ) -> list[UIACandidate]:
        """
        Find the strongest UIA candidates for a natural-language target.

        Top-level windows are searched globally first. UI controls are
        then searched inside the foreground application and other
        top-level windows.
        """

        if not isinstance(
            target,
            str,
        ):
            raise TypeError(
                "target must be a string."
            )

        target = target.strip()

        if not target:
            raise ValueError(
                "target cannot be empty."
            )

        if max_candidates <= 0:
            raise ValueError(
                "max_candidates must be greater than zero."
            )

        (
            search_target,
            requested_control_type,
        ) = self._parse_target(
            target
        )

        target_normalized = (
            self._normalize_text(
                search_target
            )
        )

        target_tokens = set(
            target_normalized.split()
        )

        # ----------------------------------------------------
        # 1. Global top-level Window search.
        # ----------------------------------------------------

        window_candidates = (
            self._find_top_level_window_candidates(
                search_target=search_target,
                target_normalized=target_normalized,
                target_tokens=target_tokens,
                area=area,
                max_candidates=max_candidates,
            )
        )

        if window_candidates:
            return window_candidates

        # ----------------------------------------------------
        # 2. Foreground application search.
        # ----------------------------------------------------

        foreground = (
            self._get_foreground_element()
        )

        if foreground is not None:

            candidates = (
                self._search_scope(
                    root=foreground,
                    original_target=target,
                    search_target=search_target,
                    target_normalized=target_normalized,
                    target_tokens=target_tokens,
                    requested_control_type=(
                        requested_control_type
                    ),
                    area=area,
                )
            )

            strong_candidates = [
                candidate
                for candidate in candidates
                if candidate.confidence >= 0.75
            ]

            if strong_candidates:
                return self._top_candidates(
                    strong_candidates,
                    max_candidates,
                )

        # ----------------------------------------------------
        # 3. Search other top-level windows.
        # ----------------------------------------------------

        results: list[
            UIACandidate
        ] = []

        windows = (
            self._get_top_level_windows()
        )

        for window in windows:

            if self._is_same_window_as_foreground(
                window
            ):
                continue

            candidates = (
                self._search_scope(
                    root=window,
                    original_target=target,
                    search_target=search_target,
                    target_normalized=target_normalized,
                    target_tokens=target_tokens,
                    requested_control_type=(
                        requested_control_type
                    ),
                    area=area,
                )
            )

            if not candidates:
                continue

            results.extend(
                candidates
            )

            results = (
                self._top_candidates(
                    results,
                    max_candidates,
                )
            )

            if (
                results
                and results[0].confidence >= 0.95
            ):
                return results

        # ----------------------------------------------------
        # 4. Expose only candidates above the public threshold.
        # ----------------------------------------------------

        results = [
            candidate
            for candidate in results
            if candidate.confidence >= 0.75
        ]

        return self._top_candidates(
            results,
            max_candidates,
        )

    # ========================================================
    # TOP-LEVEL WINDOWS
    # ========================================================

    def _find_top_level_window_candidates(
        self,
        search_target: str,
        target_normalized: str,
        target_tokens: set[str],
        area: Optional[
            tuple[int, int, int, int]
        ],
        max_candidates: int,
    ) -> list[UIACandidate]:
        """
        Search direct desktop children for top-level Window elements.

        Minimized/off-screen windows are retained.
        """

        windows = (
            self._get_top_level_windows()
        )

        exact_candidates: list[
            UIACandidate
        ] = []

        semantic_candidates: list[
            UIACandidate
        ] = []

        fuzzy_candidates: list[
            UIACandidate
        ] = []

        for window in windows:

            info = (
                self._extract_cached_element_info(
                    window
                )
            )

            if info is None:
                continue

            if (
                info.control_type
                != "Window"
            ):
                continue

            if not self._inside_area(
                info.bounding_rectangle,
                area,
            ):
                continue

            if self._is_zero_rectangle(
                info.bounding_rectangle
            ):
                continue

            name = (
                self._normalize_text(
                    info.name or ""
                )
            )

            automation_id = (
                self._normalize_text(
                    info.automation_id or ""
                )
            )

            if name == target_normalized:

                exact_candidates.append(
                    UIACandidate(
                        element=info,
                        confidence=1.0,
                    )
                )

                continue

            if (
                target_normalized
                and target_normalized in name
            ):

                semantic_candidates.append(
                    UIACandidate(
                        element=info,
                        confidence=0.95,
                    )
                )

                continue

            if (
                target_normalized
                and target_normalized in automation_id
            ):

                semantic_candidates.append(
                    UIACandidate(
                        element=info,
                        confidence=0.90,
                    )
                )

                continue

            if (
                target_tokens
                and target_tokens.issubset(
                    set(name.split())
                )
            ):

                fuzzy_candidates.append(
                    UIACandidate(
                        element=info,
                        confidence=0.82,
                    )
                )

        candidates = (
            exact_candidates
            + semantic_candidates
            + fuzzy_candidates
        )

        candidates.sort(
            key=lambda candidate: (
                candidate.confidence
            ),
            reverse=True,
        )

        return candidates[
            :max_candidates
        ]

    # ========================================================
    # TARGET PARSING
    # ========================================================

    @classmethod
    def _parse_target(
        cls,
        target: str,
    ) -> tuple[str, Optional[str]]:
        """
        Separate semantic target text from a natural-language control
        type.
        """

        normalized = cls._normalize_text(
            target
        )

        if not normalized:
            return "", None

        tokens = normalized.split()

        requested_control_type: Optional[
            str
        ] = None

        aliases = sorted(
            cls._CONTROL_TYPE_ALIASES.items(),
            key=lambda item: len(
                item[0].split()
            ),
            reverse=True,
        )

        for alias, control_type in aliases:

            alias_tokens = alias.split()

            if len(tokens) < len(
                alias_tokens
            ):
                continue

            if tokens[
                -len(alias_tokens):
            ] == alias_tokens:

                remaining = tokens[
                    :-len(alias_tokens)
                ]

                if not remaining:
                    continue

                requested_control_type = (
                    control_type
                )

                tokens = remaining

                break

        while tokens and tokens[0] in {
            "the",
            "a",
            "an",
        }:

            tokens.pop(0)

        return (
            " ".join(tokens),
            requested_control_type,
        )

    # ========================================================
    # SEARCH PIPELINE
    # ========================================================

    def _search_scope(
        self,
        root,
        original_target: str,
        search_target: str,
        target_normalized: str,
        target_tokens: set[str],
        requested_control_type: Optional[str],
        area: Optional[
            tuple[int, int, int, int]
        ],
    ) -> list[UIACandidate]:
        """
        Search one UIA subtree using increasingly broader matching.
        """

        # ----------------------------------------------------
        # A. Exact original Name.
        # ----------------------------------------------------

        exact_original = (
            self._find_first_by_property(
                root=root,
                property_id=self._name_property,
                value=original_target,
                flags=IGNORE_CASE,
            )
        )

        exact_original_info = (
            self._usable_cached_element(
                exact_original,
                area,
            )
        )

        if exact_original_info is not None:

            confidence = (
                self._calculate_confidence(
                    exact_original_info,
                    target_normalized,
                    target_tokens,
                    requested_control_type,
                )
            )

            if confidence >= 0.75:

                return [
                    UIACandidate(
                        element=exact_original_info,
                        confidence=round(
                            confidence,
                            3,
                        ),
                    )
                ]

        # ----------------------------------------------------
        # B. Exact semantic Name.
        # ----------------------------------------------------

        if (
            search_target
            and search_target.casefold()
            != original_target.casefold()
        ):

            exact_semantic = (
                self._find_first_by_property(
                    root=root,
                    property_id=self._name_property,
                    value=search_target,
                    flags=IGNORE_CASE,
                )
            )

            exact_semantic_info = (
                self._usable_cached_element(
                    exact_semantic,
                    area,
                )
            )

            if exact_semantic_info is not None:

                confidence = (
                    self._calculate_confidence(
                        exact_semantic_info,
                        target_normalized,
                        target_tokens,
                        requested_control_type,
                    )
                )

                if confidence >= 0.75:

                    return [
                        UIACandidate(
                            element=exact_semantic_info,
                            confidence=round(
                                confidence,
                                3,
                            ),
                        )
                    ]

        # ----------------------------------------------------
        # C. Exact AutomationId.
        # ----------------------------------------------------

        exact_id = (
            self._find_first_by_property(
                root=root,
                property_id=self._automation_id_property,
                value=search_target,
                flags=IGNORE_CASE,
            )
        )

        exact_id_info = (
            self._usable_cached_element(
                exact_id,
                area,
            )
        )

        if exact_id_info is not None:

            confidence = (
                self._calculate_confidence(
                    exact_id_info,
                    target_normalized,
                    target_tokens,
                    requested_control_type,
                )
            )

            if confidence >= 0.75:

                return [
                    UIACandidate(
                        element=exact_id_info,
                        confidence=round(
                            max(
                                confidence,
                                0.90,
                            ),
                            3,
                        )
                    )
                ]

        # ----------------------------------------------------
        # D. Full substring.
        # ----------------------------------------------------

        substring = (
            self._find_all_by_property(
                root=root,
                property_id=self._name_property,
                value=search_target,
                flags=(
                    IGNORE_CASE
                    | MATCH_SUBSTRING
                ),
            )
        )

        candidates = (
            self._score_cached_elements(
                elements=substring,
                target_normalized=target_normalized,
                target_tokens=target_tokens,
                requested_control_type=(
                    requested_control_type
                ),
                area=area,
            )
        )

        if candidates:

            return self._top_candidates(
                candidates,
                TOP_CANDIDATES,
            )

        # ----------------------------------------------------
        # E. Special semantic queries.
        # ----------------------------------------------------

        semantic_queries = (
            self._build_semantic_queries(
                search_target
            )
        )

        for query in semantic_queries:

            elements = (
                self._find_all_by_property(
                    root=root,
                    property_id=self._name_property,
                    value=query,
                    flags=(
                        IGNORE_CASE
                        | MATCH_SUBSTRING
                    ),
                )
            )

            candidates.extend(
                self._score_cached_elements(
                    elements=elements,
                    target_normalized=target_normalized,
                    target_tokens=target_tokens,
                    requested_control_type=(
                        requested_control_type
                    ),
                    area=area,
                )
            )

            candidates = (
                self._top_candidates(
                    candidates,
                    TOP_CANDIDATES,
                )
            )

            if (
                candidates
                and candidates[0].confidence >= 0.95
            ):

                break

        # ----------------------------------------------------
        # F. Meaningful token searches.
        # ----------------------------------------------------

        if not candidates:

            tokens = (
                self._meaningful_search_tokens(
                    target_tokens
                )
            )

            for token in tokens:

                elements = (
                    self._find_all_by_property(
                        root=root,
                        property_id=self._name_property,
                        value=token,
                        flags=(
                            IGNORE_CASE
                            | MATCH_SUBSTRING
                        ),
                    )
                )

                candidates.extend(
                    self._score_cached_elements(
                        elements=elements,
                        target_normalized=target_normalized,
                        target_tokens=target_tokens,
                        requested_control_type=(
                            requested_control_type
                        ),
                        area=area,
                    )
                )

                candidates = (
                    self._top_candidates(
                        candidates,
                        TOP_CANDIDATES,
                    )
                )

        return self._top_candidates(
            candidates,
            TOP_CANDIDATES,
        )

    # ========================================================
    # NATIVE UIA SEARCH
    # ========================================================

    def _find_first_by_property(
        self,
        root,
        property_id: int,
        value: str,
        flags: int,
    ):
        """
        Use native UIA FindFirstBuildCache with a property condition.
        """

        if not value:
            return None

        try:

            condition = (
                self._automation.CreatePropertyConditionEx(
                    property_id,
                    value,
                    flags,
                )
            )

            return root.FindFirstBuildCache(
                TREE_SCOPE_ELEMENT
                | TREE_SCOPE_DESCENDANTS,
                condition,
                self._element_cache,
            )

        except Exception:

            return None

    def _find_all_by_property(
        self,
        root,
        property_id: int,
        value: str,
        flags: int,
    ):
        """
        Use native UIA FindAllBuildCache with a property condition.
        """

        if not value:
            return None

        try:

            condition = (
                self._automation.CreatePropertyConditionEx(
                    property_id,
                    value,
                    flags,
                )
            )

            return root.FindAllBuildCache(
                TREE_SCOPE_DESCENDANTS,
                condition,
                self._element_cache,
            )

        except Exception:

            return None

    # ========================================================
    # SEMANTIC QUERY GENERATION
    # ========================================================

    @staticmethod
    def _build_semantic_queries(
        target: str,
    ) -> list[str]:
        """
        Convert common natural-language representations into likely
        UI labels.
        """

        normalized = (
            UIAInformation._normalize_text(
                target
            )
        )

        queries: list[str] = []

        drive_match = re.fullmatch(
            r"([a-z])\s+(drive|disk)",
            normalized,
        )

        if drive_match:

            letter = (
                drive_match.group(1)
            )

            queries.extend(
                [
                    f"{letter}:",
                    f"({letter}:",
                    f"{letter}):",
                ]
            )

        return queries

    @staticmethod
    def _meaningful_search_tokens(
        tokens: set[str],
    ) -> list[str]:
        """
        Return useful search tokens while excluding common filler words.
        """

        ignored = {
            "the",
            "a",
            "an",
            "to",
            "of",
            "in",
            "on",
            "and",
            "or",
        }

        return [
            token
            for token in tokens
            if len(token) >= 2
            and token not in ignored
        ]

    # ========================================================
    # CANDIDATE PROCESSING
    # ========================================================

    def _score_cached_elements(
        self,
        elements,
        target_normalized: str,
        target_tokens: set[str],
        requested_control_type: Optional[str],
        area: Optional[
            tuple[int, int, int, int]
        ],
    ) -> list[UIACandidate]:
        """
        Convert native UIA results into ranked Python candidates.
        """

        if elements is None:
            return []

        try:

            count = elements.Length

        except Exception:

            return []

        heap: list[
            tuple[
                float,
                int,
                UIACandidate,
            ]
        ] = []

        counter = 0

        for index in range(
            count
        ):

            try:

                element = (
                    elements.GetElement(
                        index
                    )
                )

                info = (
                    self._extract_cached_element_info(
                        element
                    )
                )

                if info is None:
                    continue

                if not self._inside_area(
                    info.bounding_rectangle,
                    area,
                ):
                    continue

                if self._is_zero_rectangle(
                    info.bounding_rectangle
                ):
                    continue

                confidence = (
                    self._calculate_confidence(
                        info,
                        target_normalized,
                        target_tokens,
                        requested_control_type,
                    )
                )

                if confidence <= 0.0:
                    continue

                candidate = UIACandidate(
                    element=info,
                    confidence=round(
                        confidence,
                        3,
                    ),
                )

                counter += 1

                heapq.heappush(
                    heap,
                    (
                        candidate.confidence,
                        counter,
                        candidate,
                    ),
                )

                if len(heap) > TOP_CANDIDATES:
                    heapq.heappop(heap)

            except Exception:
                continue

        candidates = [
            item[2]
            for item in heap
        ]

        candidates.sort(
            key=lambda item: (
                item.confidence
            ),
            reverse=True,
        )

        return candidates

    def _usable_cached_element(
        self,
        element,
        area: Optional[
            tuple[int, int, int, int]
        ],
    ) -> Optional[UIAElementInfo]:
        """
        Safely convert one cached UIA element into UIAElementInfo.

        Off-screen status alone does not invalidate an element.
        """

        info = (
            self._extract_cached_element_info(
                element
            )
        )

        if info is None:
            return None

        if not self._inside_area(
            info.bounding_rectangle,
            area,
        ):
            return None

        if self._is_zero_rectangle(
            info.bounding_rectangle
        ):
            return None

        return info

    def _extract_cached_element_info(
        self,
        element,
    ) -> Optional[UIAElementInfo]:
        """
        Read cached UIA properties and calculate the center and its
        virtual-desktop validity.
        """

        if element is None:
            return None

        try:

            rectangle = (
                element.CachedBoundingRectangle
            )

            control_type = (
                element.CachedControlType
            )

            if (
                rectangle is None
                or control_type is None
            ):
                return None

            bounding_rectangle = (
                float(rectangle.left),
                float(rectangle.top),
                float(rectangle.right),
                float(rectangle.bottom),
            )

            center = (
                self._calculate_center(
                    bounding_rectangle
                )
            )

            center_in_virtual_desktop = (
                center is not None
                and self._point_in_virtual_desktop(
                    center[0],
                    center[1],
                )
            )

            return UIAElementInfo(
                name=(
                    element.CachedName
                    or None
                ),
                control_type=(
                    self._control_type_name(
                        control_type
                    )
                ),
                automation_id=(
                    element.CachedAutomationId
                    or None
                ),
                bounding_rectangle=(
                    bounding_rectangle
                ),
                is_offscreen=bool(
                    element.CachedIsOffscreen
                ),
                center=center,
                center_in_virtual_desktop=(
                    center_in_virtual_desktop
                ),
            )

        except Exception:

            return None

    # ========================================================
    # WINDOWS
    # ========================================================

    def _get_foreground_element(
        self,
    ):
        """
        Return the UIA element corresponding to the foreground HWND.
        """

        hwnd = (
            self._user32.GetForegroundWindow()
        )

        if not hwnd:
            return None

        try:

            return (
                self._automation.ElementFromHandle(
                    hwnd
                )
            )

        except Exception:

            return None

    def _get_foreground_hwnd(
        self,
    ) -> int:
        """
        Return the current foreground window handle.
        """

        return int(
            self._user32.GetForegroundWindow()
        )

    def _is_same_window_as_foreground(
        self,
        element,
    ) -> bool:
        """
        Determine whether a top-level UIA element is the foreground
        window.
        """

        foreground_hwnd = (
            self._get_foreground_hwnd()
        )

        if not foreground_hwnd:
            return False

        try:

            window_handle = (
                element.CurrentNativeWindowHandle
            )

            return (
                int(window_handle)
                == foreground_hwnd
            )

        except Exception:

            return False

    def _get_top_level_windows(
        self,
    ) -> list:
        """
        Return direct desktop-child Window elements.

        Both visible and off-screen/minimized UIA windows are retained.
        """

        condition = (
            self._automation.CreatePropertyCondition(
                self._control_type_property,
                WINDOW_CONTROL_TYPE,
            )
        )

        try:

            elements = (
                self._root.FindAllBuildCache(
                    TREE_SCOPE_CHILDREN,
                    condition,
                    self._window_cache,
                )
            )

        except Exception:

            return []

        if elements is None:
            return []

        try:

            count = elements.Length

        except Exception:

            return []

        windows = []

        for index in range(
            count
        ):

            try:

                element = (
                    elements.GetElement(
                        index
                    )
                )

                if element is None:
                    continue

                windows.append(
                    element
                )

            except Exception:
                continue

        return windows

    def _get_visible_top_level_windows(
        self,
    ) -> list:
        """
        Backward-compatible alias for top-level UIA window discovery.

        Off-screen/minimized windows remain included.
        """

        return self._get_top_level_windows()

    # ========================================================
    # VIRTUAL DESKTOP
    # ========================================================

    def get_virtual_desktop_bounds(
        self,
    ) -> tuple[int, int, int, int]:
        """
        Return the Windows virtual-desktop rectangle.

        Returns:
            (left, top, right, bottom)
        """

        left = int(
            self._user32.GetSystemMetrics(
                76
            )
        )

        top = int(
            self._user32.GetSystemMetrics(
                77
            )
        )

        width = int(
            self._user32.GetSystemMetrics(
                78
            )
        )

        height = int(
            self._user32.GetSystemMetrics(
                79
            )
        )

        right = (
            left + width
        )

        bottom = (
            top + height
        )

        return (
            left,
            top,
            right,
            bottom,
        )

    def _point_in_virtual_desktop(
        self,
        x: int,
        y: int,
    ) -> bool:
        """
        Check whether a coordinate belongs to the Windows virtual
        desktop.
        """

        (
            left,
            top,
            right,
            bottom,
        ) = self.get_virtual_desktop_bounds()

        return (
            left <= x < right
            and top <= y < bottom
        )

    @staticmethod
    def _calculate_center(
        rectangle: Optional[
            tuple[float, float, float, float]
        ],
    ) -> Optional[
        tuple[int, int]
    ]:
        """
        Calculate the center of an LTRB bounding rectangle.
        """

        if rectangle is None:
            return None

        left, top, right, bottom = rectangle

        return (
            round(
                (left + right) / 2
            ),
            round(
                (top + bottom) / 2
            ),
        )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    def _calculate_confidence(
        self,
        candidate: UIAElementInfo,
        target_normalized: str,
        target_tokens: set[str],
        requested_control_type: Optional[str],
    ) -> float:
        """
        Calculate confidence from name, AutomationId, control type,
        and actionable geometry.

        Exact Window matches receive the highest confidence.

        Exact non-Window matches can still be valid, but an off-screen
        or geometrically invalid non-Window element is never promoted
        to a verified target.
        """

        name = (
            self._normalize_text(
                candidate.name or ""
            )
        )

        automation_id = (
            self._normalize_text(
                candidate.automation_id or ""
            )
        )

        control_type = (
            candidate.control_type
        )

        # ----------------------------------------------------
        # Explicit control type constraint.
        # ----------------------------------------------------

        if requested_control_type is not None:

            if (
                control_type
                != requested_control_type
            ):
                return 0.0

        # ----------------------------------------------------
        # Exact name.
        # ----------------------------------------------------

        if name == target_normalized:

            # A real top-level Window is the strongest possible
            # match for an application/window target.
            if control_type == "Window":

                return 1.0

            # Non-window exact matches are still useful, but they
            # must be physically actionable to receive high confidence.
            if (
                candidate.is_offscreen
                or not candidate.center_in_virtual_desktop
            ):

                return 0.60

            return 0.90

        # ----------------------------------------------------
        # Strong substring.
        # ----------------------------------------------------

        if (
            target_normalized
            and target_normalized in name
        ):

            if (
                candidate.is_offscreen
                or not candidate.center_in_virtual_desktop
            ):

                return 0.55

            if control_type == "Window":

                return 0.95

            return 0.85

        # ----------------------------------------------------
        # AutomationId match.
        # ----------------------------------------------------

        if (
            target_normalized
            and target_normalized in automation_id
        ):

            if (
                candidate.is_offscreen
                or not candidate.center_in_virtual_desktop
            ):

                return 0.55

            return 0.90

        # ----------------------------------------------------
        # Drive semantics.
        # ----------------------------------------------------

        if self._is_drive_target(
            target_normalized
        ):

            if self._contains_drive_reference(
                name,
                target_normalized,
            ):

                if (
                    candidate.is_offscreen
                    or not candidate.center_in_virtual_desktop
                ):

                    return 0.55

                return 0.90

        # ----------------------------------------------------
        # All target tokens.
        # ----------------------------------------------------

        candidate_tokens = set(
            name.split()
        )

        if (
            target_tokens
            and target_tokens.issubset(
                candidate_tokens
            )
        ):

            if (
                candidate.is_offscreen
                or not candidate.center_in_virtual_desktop
            ):

                return 0.55

            score = 0.82

            if self._is_interactive(
                control_type
            ):

                score += 0.05

            if control_type == "Window":

                score += 0.05

            return min(
                score,
                0.90,
            )

        # ----------------------------------------------------
        # Partial token overlap.
        # ----------------------------------------------------

        overlap = (
            target_tokens
            & candidate_tokens
        )

        if not overlap:
            return 0.0

        token_ratio = (
            len(overlap)
            / len(target_tokens)
        )

        return min(
            token_ratio * 0.45,
            0.60,
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _inside_area(
        rectangle: Optional[
            tuple[float, float, float, float]
        ],
        area: Optional[
            tuple[int, int, int, int]
        ],
    ) -> bool:
        """
        Check whether a rectangle intersects the requested search area.
        """

        if rectangle is None:
            return False

        if area is None:
            return True

        left, top, right, bottom = rectangle

        (
            area_left,
            area_top,
            area_right,
            area_bottom,
        ) = area

        return not (
            right <= area_left
            or left >= area_right
            or bottom <= area_top
            or top >= area_bottom
        )

    @staticmethod
    def _is_zero_rectangle(
        rectangle: Optional[
            tuple[float, float, float, float]
        ],
    ) -> bool:
        """
        Reject an empty or invalid bounding rectangle.
        """

        if rectangle is None:
            return True

        left, top, right, bottom = rectangle

        return (
            right <= left
            or bottom <= top
        )

    @staticmethod
    def _is_offscreen(
        element,
    ) -> bool:
        """
        Safely read the cached UIA off-screen state.
        """

        if element is None:
            return False

        try:

            return bool(
                element.CachedIsOffscreen
            )

        except Exception:

            return False

    @staticmethod
    def _is_interactive(
        control_type: Optional[str],
    ) -> bool:
        """
        Determine whether a control type is normally actionable.
        """

        return control_type in {
            "Button",
            "ListItem",
            "TreeItem",
            "MenuItem",
            "Hyperlink",
            "TabItem",
            "Edit",
            "ComboBox",
            "CheckBox",
            "RadioButton",
            "SplitButton",
        }

    @staticmethod
    def _is_drive_target(
        target: str,
    ) -> bool:
        """
        Detect natural-language drive targets.
        """

        return bool(
            re.fullmatch(
                r"[a-z]\s+(drive|disk)",
                target,
            )
        )

    @staticmethod
    def _contains_drive_reference(
        candidate: str,
        target: str,
    ) -> bool:
        """
        Check whether candidate text refers to the requested drive.
        """

        match = re.fullmatch(
            r"([a-z])\s+(drive|disk)",
            target,
        )

        if match is None:
            return False

        letter = (
            match.group(1)
        )

        patterns = (
            rf"\b{letter}\s*:",
            rf"\b{letter}\s+drive\b",
            rf"\b{letter}\s+disk\b",
        )

        return any(
            re.search(
                pattern,
                candidate,
            )
            for pattern in patterns
        )

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        """
        Normalize UI text for semantic matching.
        """

        text = text.casefold()

        text = re.sub(
            r"[^a-z0-9]+",
            " ",
            text,
        )

        return " ".join(
            text.split()
        )

    @staticmethod
    def _top_candidates(
        candidates: list[UIACandidate],
        limit: int,
    ) -> list[UIACandidate]:
        """
        Keep only the strongest UIA candidates.
        """

        candidates.sort(
            key=lambda candidate: (
                candidate.confidence
            ),
            reverse=True,
        )

        return candidates[
            :limit
        ]

    @staticmethod
    def _control_type_name(
        control_type_id: int,
    ) -> Optional[str]:
        """
        Convert a UIA control type ID into a readable control type name.
        """

        control_types = {
            50000: "Button",
            50001: "Calendar",
            50002: "CheckBox",
            50003: "ComboBox",
            50004: "Edit",
            50005: "Hyperlink",
            50006: "Image",
            50007: "ListItem",
            50008: "List",
            50009: "Menu",
            50010: "MenuBar",
            50011: "MenuItem",
            50012: "ProgressBar",
            50013: "RadioButton",
            50014: "ScrollBar",
            50015: "Slider",
            50016: "Spinner",
            50017: "StatusBar",
            50018: "Tab",
            50019: "TabItem",
            50020: "Text",
            50021: "ToolBar",
            50022: "ToolTip",
            50023: "Tree",
            50024: "TreeItem",
            50025: "Custom",
            50026: "Group",
            50027: "Thumb",
            50028: "DataGrid",
            50029: "DataItem",
            50030: "Document",
            50031: "SplitButton",
            50032: "Window",
            50033: "Pane",
            50034: "Header",
            50035: "HeaderItem",
            50036: "Table",
            50037: "TitleBar",
            50038: "Separator",
        }

        return control_types.get(
            control_type_id
        )

    # ========================================================
    # CLEANUP
    # ========================================================

    def close(
        self,
    ) -> None:
        """
        Release the COM initialization owned by this instance.
        """

        try:

            comtypes.CoUninitialize()

        except Exception:

            pass