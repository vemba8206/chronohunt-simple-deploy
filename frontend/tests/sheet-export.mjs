// Existing Apps Script helpers executed against an isolated SpreadsheetApp fixture.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

const token = 'fixture-token-only-not-production-'.repeat(2)
let rows = [], accesses = 0
const properties = {
  CHRONOHUNT_API_TOKEN: token, CHRONOHUNT_SPREADSHEET_ID: 'EXISTING-FIXTURE-SHEET',
  CHRONOHUNT_RESPONSE_SHEET: 'Form Responses 1',
}
const context = vm.createContext({ Date, JSON, String, isNaN,
  PropertiesService: { getScriptProperties: () => ({ getProperty: name => properties[name] }) },
  ContentService: { MimeType: { JSON: 'application/json' }, createTextOutput: text => ({text, setMimeType() { return this }}) },
  SpreadsheetApp: { openById(id) { accesses++; assert.equal(id,properties.CHRONOHUNT_SPREADSHEET_ID); return { getSheetByName(name) { assert.equal(name,properties.CHRONOHUNT_RESPONSE_SHEET); return { getDataRange:()=>({getValues:()=>rows}), getLastRow:()=>rows.length } } } } },
})
for (const file of ['secure_webapp.gs','registration_export.gs']) {
  vm.runInContext(await readFile(new URL('../../backend/google/' + file,import.meta.url),'utf8'),context)
}
const post = givenToken => JSON.parse(context.doPost({postData:{contents:JSON.stringify({token:givenToken})}}).text)
let count = 0
const check = (name,fn) => {fn(); count++; console.log('PASS ' + name)}
rows = [['New question','TEAM ID','Other question','Timestamp'], ['ignore',' ch01 ','ignore',new Date('2026-10-09T12:30:00Z')], ['', 'CH02','',null], ['','','',''], ['', 'CH03','',new Date('2026-10-09T12:40:00Z')]]
let result = post(token)
check('header-based lookup survives irrelevant question additions/reordering',()=>assert.equal(result.data[0].team_id,'CH01'))
check('full Sheet range exported, not first response only',()=>assert.equal(result.count,3))
check('coverage counts include invalid relevant rows',()=>assert.equal(result.total_rows_read,3))
check('original registration time preserved as UTC ISO',()=>assert.equal(result.data[0].form_timestamp,'2026-10-09T12:30:00.000Z'))
check('missing timestamp flagged without fabrication',()=>assert.equal(result.data[1].form_timestamp,null))
check('source row numbers retained while blank rows ignored',()=>assert.deepEqual(Array.from(result.data,x=>x.row_number),[2,3,5]))
check('only minimum row fields returned',()=>assert.deepEqual(Object.keys(result.data[0]).sort(),['form_timestamp','row_number','team_id']))
accesses=0
check('GET denied',()=>assert.equal(JSON.parse(context.doGet().text).success,false))
check('wrong token denied',()=>assert.equal(post('incorrect').success,false))
check('unauthorized requests never read the Sheet',()=>assert.equal(accesses,0))
rows=[['Timestamp','Team ID']]
result=post(token)
check('header-only Sheet returns verified empty export',()=>{assert.equal(result.success,true);assert.equal(result.count,0);assert.equal(result.total_rows_read,0)})
rows=[['Timestamp','Timestamp','Team ID']]
check('ambiguous timestamp headers rejected',()=>assert.equal(post(token).success,false))
rows=[['Other','Team ID']]
check('missing required header rejected',()=>assert.equal(post(token).success,false))
console.log(`\n${count} isolated Apps Script export checks passed.`)
