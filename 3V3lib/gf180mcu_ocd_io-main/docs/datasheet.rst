1.0 Introduction
================

This document serves as the data sheet for **Open Circuit Design 0.18µm (5.0V) Process 5V pad / 3.3V core Inline non-CUP GPIO Library.**  This library is a derivative of the original foundry cell library GlobalFoundries 0.18µm Green (5.0V) Process 5V Wide-Range Inline non-CUP GPIO Library.** This I/O cell library consists of bidirectional and input only I/O pad cells; analogue signal pad cells; I/O supply and ground pad cells; core supply and ground pad cells; corner, filler and breaker pad cells.  It differs from the original foundry library by placing level shifters in front of all core-facing signals, so that on the core side, all signaling is done in the 3.3V voltage domain.  The DVDD/DVSS domain is 5V, and the VDD/VSS domain is 3.3V.  There are separate pads for supplying power and ground return for each of the domains.

1.1 Cell List
-------------


.. csv-table::
   :file: specs/02_Cell_List.csv

.. note::

    gf180mcu_ocd_io__fillnc can't be used as a standalone cell and it must be used with gf180mcu_ocd_io__filln (n>=2).

1.2 Device List
---------------

nmos_6p0, pmos_6p0, pn_6p0, np_6p0, ppolyf_u, nmoscap_6p0, nmos_6p0_sab, pmos_6p0_sab, nmos_3p3, pmos_3p3.

1.3 Design Manual
-----------------

This design is based on :ref:`DESIGN MANUAL`

