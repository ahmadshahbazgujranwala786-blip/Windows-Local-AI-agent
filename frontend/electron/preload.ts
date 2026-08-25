import { contextBridge, ipcRenderer } from 'electron';
contextBridge.exposeInMainWorld('airi', {
	backendUrl: () => ipcRenderer.invoke('backend-url'),
	showMain: () => ipcRenderer.send('show-main'),
	windowControl: (action: 'minimize' | 'maximize' | 'close') => ipcRenderer.send('window-control', action),
	bubbleDragStart: (point: { x: number; y: number }) => ipcRenderer.send('bubble-drag-start', point),
	bubbleDragMove: (point: { x: number; y: number }) => ipcRenderer.send('bubble-drag-move', point),
});