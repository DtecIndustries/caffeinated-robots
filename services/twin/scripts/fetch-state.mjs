import { fetchWorldStateFromDb } from '../server/fetch-state.mjs';

const state = await fetchWorldStateFromDb();
console.log(JSON.stringify(state, null, 2));
