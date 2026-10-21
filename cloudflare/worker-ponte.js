// Ponte entre o site (GitHub Pages) e o Workers AI da Cloudflare.
// Configuração no painel do Worker: associação "Workers AI" com nome AI e segredo CHAVE_ACESSO.
// Só aceita chamadas do seu site e com a sua chave de acesso.
const ORIGEM = "https://viniciusofsilva00-code.github.io";

export default {
  async fetch(request, env) {
    const cors = {
      "Access-Control-Allow-Origin": ORIGEM,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Max-Age": "86400",
      "Vary": "Origin",
    };
    const json = (obj, status = 200) =>
      new Response(JSON.stringify(obj), {
        status,
        headers: { ...cors, "Content-Type": "application/json; charset=utf-8" },
      });

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "POST") return json({ erro: "use POST" }, 405);
    if (request.headers.get("Origin") !== ORIGEM) return json({ erro: "origem não permitida" }, 403);
    if (!env.CHAVE_ACESSO || request.headers.get("Authorization") !== `Bearer ${env.CHAVE_ACESSO}`)
      return json({ erro: "chave de acesso inválida" }, 401);

    let corpo;
    try { corpo = await request.json(); } catch { return json({ erro: "JSON inválido" }, 400); }
    const { modelo, prompt } = corpo || {};
    if (typeof modelo !== "string" || !modelo.startsWith("@cf/") || typeof prompt !== "string" || !prompt)
      return json({ erro: "envie {modelo: '@cf/…', prompt: '…'}" }, 400);
    if (prompt.length > 300000) return json({ erro: "prompt grande demais" }, 413);

    try {
      const r = await env.AI.run(modelo, {
        messages: [{ role: "user", content: prompt }],
        max_tokens: 8192, // o padrão do Workers AI é curto demais para a triagem
      });
      // cada família de modelo devolve o texto num campo diferente
      let texto = "";
      if (typeof r?.response === "string") texto = r.response;
      else if (r?.response != null) texto = JSON.stringify(r.response);
      else if (r?.choices?.[0]?.message?.content) texto = r.choices[0].message.content;
      else if (Array.isArray(r?.output))
        texto = r.output.flatMap((o) => o.content || []).map((c) => c.text || "").join("");
      return texto ? json({ texto }) : json({ erro: "resposta sem texto", bruto: r }, 502);
    } catch (e) {
      return json({ erro: String((e && e.message) || e) }, 502);
    }
  },
};
