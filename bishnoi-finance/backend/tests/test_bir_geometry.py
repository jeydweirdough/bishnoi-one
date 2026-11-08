from app.bir_pdf import _header

class RecordingCanvas:
    def __init__(self): self.cells=[]
    def setFillColor(self,*a): pass
    def setFont(self,*a): pass
    def drawString(self,*a): pass
    def drawCentredString(self,x,y,text): self.cells.append((x,y,text))


def test_page_one_tin_digits_are_inside_official_cells_not_on_separators():
    c=RecordingCanvas()
    _header(c,{'taxpayer':{'tin':'123-456-789','branchCode':'00000','rdoCode':'53A'},'year':2026,'quarter':1,'period':{'start':'2026-01-01','end':'2026-03-31'}},0)
    tin=[(x,t) for x,y,t in c.cells if y==828 and x<400]
    expected=[240.5,254.65,268.8,297.7,311.85,326.0,354.9,369.05,383.2]
    assert all(abs(x-e)<.01 for (x,t),e in zip(tin,expected))
    assert len(tin)==9
    assert ''.join(t for x,t in tin)=='123456789'


def test_rdo_letter_is_placed_in_three_separate_cells():
    c=RecordingCanvas()
    _header(c,{'taxpayer':{'tin':'123456789','branchCode':'00000','rdoCode':'53A'},'year':2026,'quarter':1,'period':{'start':'2026-01-01','end':'2026-03-31'}},0)
    cells=[(round(x,1),t) for x,y,t in c.cells if y==828 and x>540]
    assert cells==[(554.5,'5'),(568.8,'3'),(583.0,'A')]
