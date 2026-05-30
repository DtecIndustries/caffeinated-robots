import { defineConfig } from 'vite';
import { fetchWorldStateFromDb } from './server/fetch-state.mjs';

export default defineConfig({
  server: {
    port: 5173,
    open: true,
  },
  plugins: [
    {
      name: 'twin-readonly-api',
      configureServer(server) {
        server.middlewares.use('/api/state', async (req, res, next) => {
          if (req.method !== 'GET') {
            res.statusCode = 405;
            res.end('Method not allowed');
            return;
          }

          try {
            const state = await fetchWorldStateFromDb();
            res.setHeader('Content-Type', 'application/json');
            res.setHeader('Cache-Control', 'no-store');
            res.end(JSON.stringify(state));
          } catch (err) {
            console.error('[api/state]', err.message);
            res.statusCode = 500;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ error: err.message }));
          }
        });
      },
    },
  ],
});
