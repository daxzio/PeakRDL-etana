Hardware Interface Reports
==========================

PeakRDL-etana can generate comprehensive reports mapping RDL register definitions
to the generated flattened signal names.

Overview
--------

The ``--hwif-report`` flag generates two report formats:

* **Markdown** (``{module}_hwif.rpt``) - Human-readable table
* **CSV** (``{module}_hwif.csv``) - Machine-readable data

These reports provide traceability between RDL definitions and generated signals,
including addresses, widths, access types, and reset values.

Generated Files
---------------

When using ``--hwif-report``, the following additional files are generated:

* ``{module_name}_hwif.rpt`` - Markdown table report
* ``{module_name}_hwif.csv`` - CSV data export

Markdown Report Format
----------------------

The markdown report contains a formatted table with signal information:

.. code-block:: markdown

   # Hardware Interface Report: pmbus_apb4
   Generated from: PMBUS

   ## Input Signals (to register block)

   | Signal Name | Width | RDL Path | Address | SW Access | HW Access | Reset |
   |-------------|-------|----------|---------|-----------|-----------|-------|
   | `i_page` | [7:0] | PMBUS.PAGE.PAGE | 0x00000004 | r | w | N/A |

   ## Output Signals (from register block)

   | Signal Name | Width | RDL Path | Address | SW Access | HW Access | Reset |
   |-------------|-------|----------|---------|-----------|-----------|-------|
   | `o_capability_enable` | [0:0] | PMBUS.CAPABILITY.enable | 0x00000000 | rw | r | 0x1 |

   ## Summary

   - Total Input Signals: 1
   - Total Output Signals: 8
   - Total Signals: 9

CSV Report Format
-----------------

The CSV report provides machine-readable data for tool integration:

.. code-block:: csv

   signal_name,direction,width,rdl_path,address,sw_access,hw_access,reset_value
   i_page,input,8,PMBUS.PAGE.PAGE,0x00000004,r,w,N/A
   o_capability_enable,output,1,PMBUS.CAPABILITY.enable,0x00000000,rw,r,0x1

Column Descriptions
-------------------

* **signal_name** - Generated signal name (flattened)
* **direction** - ``input`` (to register block) or ``output`` (from register block)
* **width** - Signal width in bits
* **rdl_path** - Full hierarchical RDL path to field
* **address** - Register address in hexadecimal
* **sw_access** - Software access type (``r``, ``w``, ``rw``)
* **hw_access** - Hardware access type (``r``, ``w``, ``rw``)
* **reset_value** - Reset value in hexadecimal (``N/A`` if none)

Usage
-----

Enable report generation:

.. code-block:: bash

   peakrdl etana my_registers.rdl --hwif-report -o output/

Use Cases
---------

Signal Reference
~~~~~~~~~~~~~~~~

Quick lookup of which signal corresponds to which RDL field:

1. Open markdown report
2. Search for RDL path or signal name
3. See width, address, and access information

Hardware Integration
~~~~~~~~~~~~~~~~~~~~

Map signals to external blocks:

1. Export CSV to spreadsheet
2. Cross-reference with hardware design
3. Generate connection code

Debugging
~~~~~~~~~

Verify signal-to-address mapping:

1. Compare report with memory map
2. Verify register access patterns
3. Debug read/write issues

Test Generation
~~~~~~~~~~~~~~~

Automated test creation:

1. Import CSV to test generator
2. Create stimulus vectors
3. Verify register functionality

Example: Using CSV for Test Generation
---------------------------------------

.. code-block:: python

   import csv

   # Read hwif report
   with open('pmbus_apb4_hwif.csv') as f:
       reader = csv.DictReader(f)
       for row in reader:
           signal = row['signal_name']
           width = int(row['width'])
           address = row['address']

           # Generate test case
           print(f"Testing {signal} at {address}, width {width}")

Example: Integration Spreadsheet
---------------------------------

Import the CSV into Excel/LibreOffice to:

* Track signal connections
* Document pin assignments
* Plan board layout
* Generate connection tables

Difference from PeakRDL-regblock
---------------------------------

**PeakRDL-regblock** (struct-based):

.. code-block:: text

   hwif_in.PAGE.PAGE.next[7:0]
   hwif_out.CAPABILITY.enable.value

This format documents struct member paths, which don't apply to etana's
flattened signals.

**PeakRDL-etana** (flattened):

.. code-block:: text

   i_page,input,8,PMBUS.PAGE.PAGE,0x00000004,r,w
   o_capability_enable,output,1,PMBUS.CAPABILITY.enable,0x00000000,rw,r

This format shows actual signal names, making it directly useful for integration
and debugging.

See Also
--------

* :doc:`hwif` - Hardware interface signal reference
* :doc:`template_generation` - Integration template module
