import { SceneManager } from './scene/SceneManager.js';
import { StateSync } from './data/StateSync.js';
import { StatusPanel } from './ui/StatusPanel.js';
import { DebugPanel } from './ui/DebugPanel.js';

const canvas = document.getElementById('scene');
const hudMain = document.getElementById('hud-main');
const hudDebug = document.getElementById('hud-debug');

const scene = new SceneManager(canvas);
const panel = new StatusPanel(hudMain, {
  onQcFail: () => sync.triggerQcFail(),
  onApproveHolding: (id) => sync.approveHolding(id),
  onRejectHolding: (id) => sync.rejectHolding(id),
  onTestTransfer: (from, to) => sync.triggerTestTransfer(from, to),
});
const debugPanel = new DebugPanel(hudDebug);

const sync = new StateSync((state, meta) => {
  scene.setState(state);
  panel.render(state, meta);
  debugPanel.render(meta.debug, state);
});

sync.start();
