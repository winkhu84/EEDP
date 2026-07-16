from app.engine.address_usage_engine import (
    build_card_usage, group_digital_addresses_by_card, STATUS_USED, STATUS_SPARE, STATUS_CONFLICT,
)
from app.model.device import Device
from app.model.signal import Signal
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.ui.dialogs.address_usage_dialog import AddressUsageDialog
from app.ui.main_controller import MainController

# Test A
p101 = Device(id='a', tag='P-101', area='PRE', category='Equipment', type='Pump', description='', quantity=1, signals=[
    Signal('Local/Remote Mode','DI',False,True,address='I0.0'),
    Signal('Run Feedback','DI',True,True,address='I0.1'),
    Signal('Fault Feedback','DI',True,True,address='I0.2'),
])
cards = build_card_usage([p101], 'DI')
assert len(cards)==1
c=cards[0]
assert c.start_address=='I0.0' and c.end_address=='I3.7'
assert c.used==3 and c.spare==29 and c.conflicts==0
by={ch.address: ch.status for ch in c.channels}
assert by['I0.0']==STATUS_USED and by['I0.1']==STATUS_USED and by['I0.2']==STATUS_USED
assert by['I0.3']==STATUS_SPARE and by['I3.7']==STATUS_SPARE
assert 'P-101' in c.channels[0].tooltip() and 'Local/Remote Mode' in c.channels[0].tooltip()
print('A OK', c.used, c.spare)

# Test B
p102 = Device(id='b', tag='P-102', area='PRE', category='Equipment', type='Pump', description='', quantity=1, signals=[
    Signal('Local/Remote Mode','DI',False,True,address='I1.0'),
    Signal('Run Feedback','DI',True,True,address='I1.1'),
    Signal('Fault Feedback','DI',True,True,address='I1.2'),
])
cards = build_card_usage([p101,p102], 'DI')
assert cards[0].used==6 and cards[0].spare==26
ch=next(x for x in cards[0].channels if x.address=='I1.0')
assert 'P-102' in ch.tooltip()
print('B OK')

# Test C conflict
p101.signals[1].address='I0.1'
p102.signals[1].address='I0.1'
cards = build_card_usage([p101,p102], 'DI')
ch=next(x for x in cards[0].channels if x.address=='I0.1')
assert ch.status==STATUS_CONFLICT
tip=ch.tooltip()
assert 'Conflict detected' in tip and 'P-101' in tip and 'P-102' in tip
print('C OK')

# Test D second card
p101.signals[1].address='I0.1'
p102.signals[1].address='I1.1'
extra = Device(id='c', tag='P-201', area='PRE', category='Equipment', type='Pump', description='', quantity=1, signals=[
    Signal('Run Feedback','DI',True,True,address='I5.0'),
])
cards = build_card_usage([p101,p102,extra], 'DI')
assert len(cards)==2
assert cards[1].start_address=='I4.0' and cards[1].end_address=='I7.7'
ch=next(x for x in cards[1].channels if x.address=='I5.0')
assert ch.status==STATUS_USED
blocks=group_digital_addresses_by_card(['I0.0','I1.2','I5.0'], 'I', 32)
assert blocks==[(1,'I0.0','I3.7'),(2,'I4.0','I7.7')]
print('D OK')

# Disabled / empty ignored
idle = Device(id='d', tag='P-9', area='PRE', category='Equipment', type='Pump', description='', quantity=1, signals=[
    Signal('Run Feedback','DI',True,False,address='I0.0'),
    Signal('Fault Feedback','DI',True,True,address=''),
])
assert build_card_usage([idle], 'DI') == ()

# UI
app=QApplication([])
w=MainWindow()
assert w.property_editor.address_usage_button is not None
# stretch factors 4:6 - check layout
# open dialog
dlg=AddressUsageDialog([p101], parent=w)
assert dlg.windowTitle()=='PLC Address Usage'
c=MainController(w); c.bind()
print('UI OK')
print('ALL PASS')
