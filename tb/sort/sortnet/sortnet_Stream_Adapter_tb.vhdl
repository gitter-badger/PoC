-- EMACS settings: -*-  tab-width: 2; indent-tabs-mode: t -*-
-- vim: tabstop=2:shiftwidth=2:noexpandtab
-- kate: tab-width 2; replace-tabs off; indent-width 2;
-- 
-- =============================================================================
-- Authors:					Patrick Lehmann
--
-- Testbench:				Sorting Network: Stream_Adapter
--
-- Description:
-- ------------------------------------
--	TODO
--
-- License:
-- =============================================================================
-- Copyright 2007-2016 Technische Universitaet Dresden - Germany
--										 Chair for VLSI-Design, Diagnostics and Architecture
-- 
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
-- 
--		http://www.apache.org/licenses/LICENSE-2.0
-- 
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.
-- =============================================================================

library IEEE;
use			IEEE.STD_LOGIC_1164.all;
use			IEEE.NUMERIC_STD.all;

library PoC;
use			PoC.utils.all;
use			PoC.vectors.all;
use			PoC.physical.all;
use			PoC.sortnet.ALL;
-- simulation only packages
use			PoC.sim_types.all;
use			PoC.simulation.all;
use			PoC.waveform.all;

library OSVVM;
use			OSVVM.RandomPkg.all;


entity sortnet_Stream_Adapter_tb is
end entity;


architecture tb of sortnet_Stream_Adapter_tb is
	constant DEBUG									: BOOLEAN		:= TRUE;
	
	constant STREAM_DATA_BITS				: POSITIVE	:= ite(DEBUG, 16,	 32);

	constant SORTNET_SIZE						: POSITIVE	:= ite(DEBUG, 8,	128);
	constant SORTNET_KEY_BITS				: POSITIVE	:= ite(DEBUG, 8,	 32);
	constant SORTNET_DATA_BITS			: POSITIVE	:= ite(DEBUG, 16,	 64);

	constant LOOP_COUNT							: POSITIVE	:= ite(DEBUG, 10,	 32);	--1024);
	
	constant STAGES									: POSITIVE	:= SORTNET_SIZE;
	constant DELAY									: NATURAL		:= 50;	--STAGES / PIPELINE_STAGE_AFTER;

	constant CLOCK_FREQ							: FREQ				:= 100 MHz;
	signal Clock										: STD_LOGIC		:= '1';
	
	constant TAG_BITS								: POSITIVE		:= 2;
	signal Generator_Valid					: STD_LOGIC;
	signal Generator_Data						: STD_LOGIC_VECTOR(STREAM_DATA_BITS - 1 downto 0);
	signal Generator_IsKey					: STD_LOGIC;
	signal Generator_Tag						: STD_LOGIC_VECTOR(TAG_BITS - 1 downto 0);
	
	signal Sort_Out_Valid						: STD_LOGIC;
	signal Sort_Out_Data						: STD_LOGIC_VECTOR(STREAM_DATA_BITS - 1 downto 0);
	signal Sort_Out_IsKey						: STD_LOGIC;
	
	signal Tester_Ack								: STD_LOGIC;
	
	signal StopSimulation						: STD_LOGIC		:= '0';
begin
	-- initialize global simulation status
	simInitialize;
	
	-- generate global testbench clock
	simGenerateClock(Clock, CLOCK_FREQ);

	procGenerator : process
		constant simProcessID	: T_SIM_PROCESS_ID		:= simRegisterProcess("Generator");
		variable RandomVar	: RandomPType;								-- protected type from RandomPkg

		variable KeyInput		: STD_LOGIC_VECTOR(SORTNET_KEY_BITS - 1 downto 0);
		variable DataInput	: STD_LOGIC_VECTOR(SORTNET_DATA_BITS - SORTNET_KEY_BITS - 1 downto 0);
		
	begin
		RandomVar.InitSeed(RandomVar'instance_name);		-- Generate initial seeds
		
		Generator_Valid		<= '0';
		Generator_Data		<= (others => '0');
		Generator_IsKey		<= '0';
		Generator_Tag			<= (others => '0');
		
		wait until rising_edge(Clock);
		
		Generator_Valid		<= '1';
		for i in 0 to LOOP_COUNT - 1 loop
			Generator_IsKey	<= to_sl(i mod 2 = 0);
			Generator_Tag		<= to_slv(i mod 2, TAG_BITS);
			
			for j in 0 to SORTNET_SIZE - 1 loop
				KeyInput				:= RandomVar.RandSlv(SORTNET_KEY_BITS);
				DataInput				:= RandomVar.RandSlv(SORTNET_DATA_BITS - SORTNET_KEY_BITS);
				
				-- assemble data vector and write to stream interface
				Generator_Data	<= resize(DataInput & KeyInput, STREAM_DATA_BITS);
				
				wait until rising_edge(Clock);
			end loop;
		end loop;
		
		Generator_Valid				<= '0';
		
		simWaitUntilRisingEdge(Clock, 8);
		
		-- This process is finished
		simDeactivateProcess(simProcessID);
		wait;		-- forever
	end process;
	
	sort : entity PoC.sortnet_Stream_Adapter
		generic map (
			STREAM_DATA_BITS			=> STREAM_DATA_BITS,
			-- SORTNET_IMPL					=> SORT_SORTNET_IMPL_BITONIC_SORT,
			SORTNET_IMPL					=> SORT_SORTNET_IMPL_ODDEVEN_SORT,
			-- SORTNET_IMPL					=> SORT_SORTNET_IMPL_ODDEVEN_MERGESORT,
			SORTNET_SIZE					=> SORTNET_SIZE,
			SORTNET_KEY_BITS			=> SORTNET_KEY_BITS,
			SORTNET_DATA_BITS			=> SORTNET_DATA_BITS,
			INVERSE								=> FALSE
		)
		port map (
			Clock				=> Clock,
			Reset				=> '0',
			
			In_Valid		=> Generator_Valid,
			In_IsKey		=> Generator_IsKey,
			In_Data			=> Generator_Data,
			In_Meta			=> Generator_Tag,
			In_Ack			=> open,
			
			Out_Valid		=> Sort_Out_Valid,
			Out_IsKey		=> Sort_Out_IsKey,
			Out_Data		=> Sort_Out_Data,
			Out_Meta		=> open,
			Out_Ack			=> Tester_Ack
		);
	
	procChecker : process
		constant simProcessID	: T_SIM_PROCESS_ID		:= simRegisterProcess("Checker");
		
		variable Check			: BOOLEAN;
		variable CurValue		: UNSIGNED(SORTNET_KEY_BITS - 1 downto 0);
		variable LastValue	: UNSIGNED(SORTNET_KEY_BITS - 1 downto 0);
	begin
		report "Delay=" & INTEGER'image(DELAY) severity NOTE;
	
		Tester_Ack		<= '0';
	
		simWaitUntilRisingEdge(Clock, 8);
		
		wait until (Sort_Out_Data /= (STREAM_DATA_BITS - 1 downto 0 => '0'));
		
		Tester_Ack		<= '1';
		for i in 0 to LOOP_COUNT - 1 loop
			Check			:= TRUE;
			LastValue	:= (others => '0');
			for j in 0 to SORTNET_SIZE - 1 loop
				wait until rising_edge(Clock);
				
				if (Sort_Out_IsKey = '1') then
					CurValue	:= unsigned(Sort_Out_Data(SORTNET_KEY_BITS - 1 downto 0));
					Check			:= Check and (LastValue <= CurValue);
					LastValue	:= CurValue;
				end if;
			end loop;
			simAssertion(Check, "Result is not monotonic.");
		end loop;

		-- This process is finished
		simDeactivateProcess(simProcessID);
		wait;  -- forever
	end process;
	
end architecture;
