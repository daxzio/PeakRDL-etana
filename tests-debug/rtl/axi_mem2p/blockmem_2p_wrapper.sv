// Copyright (c) 2023, Dave Keeshan
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//     * Redistributions of source code must retain the above copyright
//       notice, this list of conditions and the following disclaimer.
//     * Redistributions in binary form must reproduce the above copyright
//       notice, this list of conditions and the following disclaimer in the
//       documentation and/or other materials provided with the distribution.
//     * Neither the name of the organization nor the
//       names of its contributors may be used to endorse or promote products
//       derived from this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
// ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
// WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY
// DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
// LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
// ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
// SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

module blockmem_2p_wrapper #(
    integer G_USEIP = 0
    , integer G_DATAWIDTH = 32
    , integer G_MEMDEPTH = 1024
    , integer G_BWENABLE = 0
    , parameter G_INIT_FILE = ""  // verilog_lint: waive explicit-parameter-storage-type (not supported in vivado)
    , integer G_ADDRWIDTH = $clog2(G_MEMDEPTH)
    //localparam integer G_PADWIDTH = ($ceil(real'(G_DATAWIDTH/ 8.0) ) * 8);
    //localparam integer G_PADWIDTH = (integer'((G_DATAWIDTH-1)/8)+1)*8;
    , integer G_PADWIDTH = (G_DATAWIDTH + 7) & ~(4'h7)
    , integer G_WEWIDTH = (((G_PADWIDTH - 1) / 8) * G_BWENABLE) + 1

) (
      input                    clka
    , input                    ena
    , input  [  G_WEWIDTH-1:0] wea
    , input  [G_ADDRWIDTH-1:0] addra
    , input  [G_DATAWIDTH-1:0] dina
    , input                    clkb
    , input                    enb
    , input  [G_ADDRWIDTH-1:0] addrb
    , output [G_DATAWIDTH-1:0] doutb
);

    generate
        if (0 == G_USEIP) begin : g_blockmem_2p
            blockmem_2p #(
                  .G_DATAWIDTH(G_DATAWIDTH)
                , .G_MEMDEPTH (G_MEMDEPTH)
                , .G_BWENABLE (G_BWENABLE)
                , .G_INIT_FILE(G_INIT_FILE)
            ) i_blockmem_2p (
                .*
            );
        end else begin : g_ip_blockmem_2p
            blockmem_2p #(
                  .G_DATAWIDTH(G_DATAWIDTH)
                , .G_MEMDEPTH (G_MEMDEPTH)
                , .G_BWENABLE (G_BWENABLE)
                , .G_INIT_FILE(G_INIT_FILE)
            ) i_blockmem_2p (
                .*
            );
        end
    endgenerate

endmodule
