export async function disclose(page, label) {
  const summary=page.getByText(label,{exact:true});
  if(!await summary.evaluate(el=>el.parentElement.open))await summary.click();
}
