/* OPTIONAL hardening template for the EXISTING Apps Script project.
 * Review before installing; do not create another Google Form or spreadsheet.
 * Rename your existing JSON-building doGet implementation to
 * readCompetitionResponse(), preserving its Timestamp/Team ID header lookup.
 * It must return the existing ContentService JSON response, not a raw object.
 * Set Script Property CHRONOHUNT_API_TOKEN to a random shared secret; put the
 * same value in the backend GOOGLE_SHEET_API_TOKEN. Never log the token.
 * Replace BOTH exported entry points so GET cannot reveal the source data.
 */
function deniedResponse() {
  return ContentService.createTextOutput(JSON.stringify({success:false,count:0,data:[]}))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet() {
  return deniedResponse();
}

function doPost(e) {
  var expected = PropertiesService.getScriptProperties().getProperty('CHRONOHUNT_API_TOKEN');
  if (!expected || expected.length < 32) return deniedResponse();
  var body;
  try { body = JSON.parse(e.postData.contents); } catch (_) { return deniedResponse(); }
  if (typeof body.token !== 'string' || body.token.length !== expected.length) return deniedResponse();
  var difference = 0;
  for (var i = 0; i < expected.length; i++) {
    difference |= expected.charCodeAt(i) ^ body.token.charCodeAt(i);
  }
  if (difference !== 0) return deniedResponse();
  return readCompetitionResponse();
}
