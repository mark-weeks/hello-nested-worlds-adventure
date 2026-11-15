// Normal invited-study journeys start with an explicitly enrolled adult.
// Entry/refusal journeys deliberately do not call this fixture helper.
export async function acknowledgeCurrentStudy(origin, key) {
  const headers = {'X-Beta-Key': key};
  const response = await fetch(origin + '/participation', {headers});
  if (!response.ok) throw new Error('Synthetic study notice could not be read.');
  const notice = await response.json();
  if (!notice.required || notice.accepted) return;
  if (!notice.ready) throw new Error('Synthetic study notice is not ready.');
  const accepted = await fetch(origin + '/participation', {method: 'POST',
    headers: {...headers, 'Content-Type': 'application/json'},
    body: JSON.stringify({accepted: true, age_confirmed: true, revision: notice.revision})});
  if (!accepted.ok || !(await accepted.json()).accepted)
    throw new Error('Synthetic adult could not acknowledge the current study notice.');
}
