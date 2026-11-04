"""Channel guidance: a printed PDF, validation and filing are different results.

No method here submits data or treats a locally generated file as BIR-accepted.
Evidence-backed validation/filing records require a separate reviewed workflow.
"""
from copy import deepcopy

GUIDANCE = {
 '2550Q': {
  'kind':'return','paper':'Official-form print copy; manual filing depends on the applicable BIR instructions.',
  'online':'Enter and validate the return in the applicable eBIRForms/eFPS form. This PDF is not an electronic return import file.',
  'attachments':'Required sales/purchase/importation lists need the applicable RELIEF format and validation, not a renamed CSV.',
  'source':'https://bir-cdn.bir.gov.ph/BIR/pdf/RMC%20No.%2049-2025.pdf'},
 '2307': {
  'kind':'certificate','paper':'Certificate for the payee, with verified identity, period, figures and authorised signatures.',
  'online':'This certificate is not a standalone eBIRForms/eFPS tax return. Supporting certificate submission follows the recipient return requirements.',
  'attachments':'SAWT/certificate attachments, when required, need their own applicable format and validation.',
  'source':'https://bir-cdn.bir.gov.ph/local/pdf/2307%20Jan%202018%20ENCS%20v3.pdf'},
 '0619E': {
  'kind':'return','paper':'Monthly remittance form for the first two calendar-quarter months, subject to the filing rules.',
  'online':'Enter and validate 0619E in eBIRForms/eFPS. Generation of this PDF does not record payment or filing.',
  'attachments':'Actual remittance evidence remains separate from calculated withholding.',
  'source':'https://efps.bir.gov.ph/efps-war/EFPSWeb_war/help/proc0619e.html'},
 '1601EQ': {
  'kind':'return','paper':'Quarterly return using the correct period and verified actual remittances.',
  'online':'Enter and validate the quarterly return in eBIRForms/eFPS; retain its filing acknowledgement separately.',
  'attachments':'QAP needs the applicable Alphalist validation and acknowledgement/validation-success evidence.',
  'source':'https://bir-cdn.bir.gov.ph/local/pdf/1601-EQ%20Guide%20January%202019%20ENCS%20rev.pdf'},
 '1604E': {
  'kind':'return','paper':'Annual return and schedules need complete-year coverage and actual remittance details.',
  'online':'Use the applicable official annual-return channel and retain filing acknowledgement.',
  'attachments':'The annual alphalist requires the applicable electronic format and validation; the PDF working table is not that file.',
  'source':'https://bir-cdn.bir.gov.ph/local/pdf/1604E%20Jan%202018%20ENCS%20Final2.pdf'},
}

def guidance(form:str)->dict:
    if form not in GUIDANCE:raise ValueError('Choose a supported BIR form.')
    return {'form':form,**deepcopy(GUIDANCE[form]),'preparationStatus':'review_draft',
            'electronicValidationStatus':'not_verified','filingEvidenceStatus':'not_recorded_in_finance',
            'readyForFiling':False,'directElectronicFileGenerated':False}
