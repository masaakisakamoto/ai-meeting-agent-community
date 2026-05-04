const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('meetingAgentDesktop', {
  version: '0.6.0',
  mode: 'desktop-alpha',
  privateCoreLoaded: false
});
