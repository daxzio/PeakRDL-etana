Template Generation
===================

PeakRDL-etana can automatically generate integration template modules that show
how to properly instantiate the generated register block.

Overview
--------

The ``--generate-template`` flag generates a complete, lintable SystemVerilog
module that demonstrates:

- Proper module port declarations (APB interface at top-level)
- Hardware interface signal declarations (internal with ``w_`` prefix)
- Complete instantiation with all connections
- Leading comma style for readability

Generated Files
---------------

When using ``--generate-template``, the following files are generated:

* ``{module_name}.sv`` - Main register block module
* ``{module_name}_example.sv`` - **Integration template** (new)

Template Structure
------------------

The template module has this structure:

.. code-block:: systemverilog

   module {module_name}_example (
            input wire clk
           ,input wire arst_n
           // APB interface
           ,input s_apb_psel
           ,input [N:0] s_apb_paddr
           ,output logic s_apb_pready
           ,output logic [31:0] s_apb_prdata
   );

       // Hardware interface signal declarations
       logic [7:0] w_page;
       logic [0:0] w_capability_enable;
       // ... all hwif signals

       // Instantiation
       {module_name} i_{module_name} (
            .clk(clk)
           ,.arst_n(arst_n)
           // APB interface
           ,.s_apb_psel(s_apb_psel)
           ,.s_apb_paddr(s_apb_paddr)
           // ... all connections
           // Hardware interface signals
           ,.i_page(w_page)
           ,.o_capability_enable(w_capability_enable)
           // ... all hwif connections
       );

   endmodule

Usage
-----

Enable template generation:

.. code-block:: bash

   peakrdl etana my_registers.rdl --generate-template -o output/

Integration Workflow
--------------------

1. Generate the register block and template:

   .. code-block:: bash

      peakrdl etana my_design.rdl --generate-template -o rtl/

2. Open the template file (``{module}_example.sv``)

3. Copy the hardware interface signal declarations

4. Copy the instantiation code

5. Paste into your top-level module

6. Connect APB signals to your CPU bus

7. Connect hardware interface signals to your peripherals

Example Integration
-------------------

.. code-block:: systemverilog

   module my_soc_top (
       input wire clk,
       input wire arst_n,
       // CPU bus
       input cpu_apb_psel,
       input [9:0] cpu_apb_paddr,
       // ...
   );

       // Hardware interface signals (from template)
       logic [7:0] w_page;
       logic [0:0] w_capability_enable;

       // Instantiation (from template)
       pmbus_apb4 i_pmbus_apb4 (
            .clk(clk)
           ,.arst_n(arst_n)
           ,.s_apb_psel(cpu_apb_psel)
           ,.s_apb_paddr(cpu_apb_paddr)
           // ...
           ,.i_page(w_page)
           ,.o_capability_enable(w_capability_enable)
       );

       // Connect to your design
       assign w_page = current_page_number;
       assign enable_output = w_capability_enable;

   endmodule

Benefits
--------

✓ **Copy-paste ready** - Legal, lintable Verilog code
✓ **Correct by construction** - Matches generated module exactly
✓ **Time-saving** - No manual signal declaration needed
✓ **Consistent style** - Leading comma format
✓ **Type-safe** - All signals properly declared

See Also
--------

* :doc:`hwif` - Hardware interface signal reference
* :doc:`hwif_report` - Signal documentation and reports
