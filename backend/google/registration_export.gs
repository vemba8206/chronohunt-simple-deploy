/* Add to the EXISTING token-authenticated Apps Script project after review.
 * Keep the secure doPost/doGet wrapper in secure_webapp.gs.
 * Script Properties identify the EXISTING spreadsheet and response tab:
 * CHRONOHUNT_SPREADSHEET_ID, CHRONOHUNT_RESPONSE_SHEET.
 * Optional header names: CHRONOHUNT_TIMESTAMP_HEADER (default Timestamp),
 * CHRONOHUNT_TEAM_HEADER (default Team ID).
 * Returns every nonempty registration row, including invalid rows for auditing.
 * No email, question answer, circuit code, or credential is exported.
 */
function readCompetitionResponse() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('CHRONOHUNT_SPREADSHEET_ID');
  var tab = props.getProperty('CHRONOHUNT_RESPONSE_SHEET');
  if (!id || !tab) return deniedResponse();
  var sheet = SpreadsheetApp.openById(id).getSheetByName(tab);
  if (!sheet) return deniedResponse();
  var rows = sheet.getDataRange().getValues();
  var header = rows[0].map(function(value) { return String(value).trim().toLowerCase(); });
  var timestampName = (props.getProperty('CHRONOHUNT_TIMESTAMP_HEADER') || 'Timestamp').trim().toLowerCase();
  var teamName = (props.getProperty('CHRONOHUNT_TEAM_HEADER') || 'Team ID').trim().toLowerCase();
  if (header.filter(function(h) { return h === timestampName; }).length !== 1 ||
      header.filter(function(h) { return h === teamName; }).length !== 1) return deniedResponse();
  var timestampIndex = header.indexOf(timestampName), teamIndex = header.indexOf(teamName);
  var data = [];
  for (var i = 1; i < rows.length; i++) {
    if (rows[i].every(function(cell) { return cell === '' || cell === null; })) continue;
    var timestamp = rows[i][timestampIndex];
    data.push({
      row_number: i + 1,
      team_id: String(rows[i][teamIndex] || '').trim().toUpperCase(),
      form_timestamp: timestamp instanceof Date && !isNaN(timestamp.getTime()) ? timestamp.toISOString() : null
    });
  }
  return ContentService.createTextOutput(JSON.stringify({
    success: true, count: data.length, total_rows_read: data.length,
    source_last_row: sheet.getLastRow(), data: data
  })).setMimeType(ContentService.MimeType.JSON);
}
