// Answer the page's first /participation request with `respond`; later ones
// reach the server. The route stays installed for the life of the page. A
// one-shot route (`{ times: 1 }`) is not equivalent: when the last route on a
// page is used up, Playwright switches request interception off, and a request
// the page sends at that moment can be left unanswered for good. These pages
// send their next request within milliseconds of the stubbed failure.
export async function failFirstNotice(page, respond) {
  let first = true;
  await page.route('**/participation', route => {
    if (!first) return route.fallback();
    first = false;
    return respond(route);
  });
}
