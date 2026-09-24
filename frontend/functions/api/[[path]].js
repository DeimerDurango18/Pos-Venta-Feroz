export async function onRequest(context) {
  const origin =
    context.env.API_ORIGIN ||
    "https://inherited-courts-print-residents.trycloudflare.com";
  const path = context.params?.path ? context.params.path.join("/") : "";
  const url = `${origin}/api${path ? "/" + path : ""}`;

  const headers = new Headers(context.request.headers);
  headers.delete("host");
  headers.delete("origin");

  const init = { method: context.request.method, headers };
  if (!["GET", "HEAD"].includes(context.request.method)) {
    init.body = await context.request.text();
  }

  const res = await fetch(url, init);
  const text = await res.text();
  return new Response(text, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") || "application/json",
    },
  });
}