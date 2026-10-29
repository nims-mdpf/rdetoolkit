"""Static inputs and generated contract snapshots for Phase G.

Phase K dynamic-oracle replacement map (``test_inventory.md`` §A):

* ``TC-GOLD-001/004/005`` and ``TC-E2E-001`` use
  ``expected/v1/invoice/ok.json``.
* ``TC-GOLD-002`` and ``TC-E2E-006`` use
  ``expected/v1/excelinvoice/ok.json``.
* ``TC-GOLD-003/006`` and ``TC-E2E-002`` use
  ``expected/v1/multidatatile/ok.json``.
* ``TC-E2E-007`` uses ``expected/v1/smarttable/ok.json`` and the real
  ``inputs/smarttable/data`` workbook tree.
* ``TC-DISPATCH-002/004/005`` use the normalized ``legacy_return`` in
  ``expected/v1/invoice/ok.json``.

The dynamic tests remain in place until Phase K. This docstring supplies the
replacement location without modifying those existing oracle tests; Session
G1 permits only TC-E2E-007's SmartTable mock-removal edit.
"""
