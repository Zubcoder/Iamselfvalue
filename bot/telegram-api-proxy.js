/**
 * Cloudflare Worker reverse proxy for the Telegram Bot API.
 *
 * Use this if your VPS/ISP blocks api.telegram.org (common in some Russian clouds).
 * The bot token never touches logs: the path is only used to build the upstream URL.
 */

const UPSTREAM = 'https://api.telegram.org';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const upstreamUrl = new URL(url.pathname + url.search, UPSTREAM);

    const reqHeaders = new Headers(request.headers);
    // Do not forward the original Host; upstream Telegram needs its own hostname.
    reqHeaders.delete('host');

    const init = {
      method: request.method,
      headers: reqHeaders,
      body: request.body,
    };

    const response = await fetch(upstreamUrl.toString(), init);

    const resHeaders = new Headers(response.headers);
    resHeaders.set('Access-Control-Allow-Origin', '*');
    resHeaders.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    resHeaders.set('Access-Control-Allow-Headers', 'Content-Type');

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: resHeaders,
    });
  },
};
