#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ctypes as ct
import time

import SLABHIDtoSMBUS as hid


class RelayController:
    def __init__(self, mux_addr=0x70):
        """
        :param mux_addr: Mux (TCA9548A等) のアドレス (7bit)。
                         標準的な 0x70 をデフォルトとしています。
        """
        self.mux_addr_8bit = mux_addr << 1

        # MCP23017 のアドレスリスト (0x20, 0x21, 0x22)
        # index 0->0x20, 1->0x21, 2->0x22
        self.mcp_addrs = [0x20, 0x21, 0x22]

        self.smb = hid.HidSmbusDevice()
        self._lib = hid._DLL
        self._setup_lib_types()

        # 状態管理用辞書
        # 構造: self.states[channel_id][mcp_addr_key] = {'a': 0xFF, 'b': 0xFF, 'initialized': False}
        self.states = {}

        self.current_mux_ch = -1  # 現在選択されているMuxチャンネル
        self.is_connected = False

    def _setup_lib_types(self):
        """DLL関数の型定義修正"""
        self._lib.HidSmbus_GetReadResponse.argtypes = [
            ct.c_void_p,
            ct.POINTER(ct.c_ubyte),
            ct.c_char_p,
            ct.c_ubyte,
            ct.POINTER(ct.c_ubyte),
        ]
        self._lib.HidSmbus_GetReadResponse.restype = ct.c_int

    def open(self):
        try:
            self.smb.Open(0)
            self.is_connected = True

            # SMBus設定
            self.smb.SetTimeouts(1000)
            self.smb.SetSmbusConfig(100000, 0x02, False, 1000, 1000, False, 3)

            print("HID/SMBus opened successfully.")
            return True
        except Exception as e:
            print(f"Connection Failed: {e}")
            self.close()
            return False

    def close(self):
        if self.is_connected and self.smb.IsOpened():
            self.smb.Close()
            self.is_connected = False
            print("RelayBoard connection closed.")

    def _switch_mux(self, channel):
        """Muxのチャンネルを切り替える"""
        if self.current_mux_ch == channel:
            return True  # 既に選択されている

        try:
            # TCA9548A等は 1 << channel ビットを立てる
            mux_data = 1 << channel
            self.smb.WriteRequest(self.mux_addr_8bit, [mux_data], 1)
            time.sleep(0.02)  # 切り替え安定待ち
            self.current_mux_ch = channel
            return True
        except Exception as e:
            print(f"Error switching Mux to ch {channel}: {e}")
            return False

    def _ensure_mcp_initialized(self, channel, mcp_idx):
        """指定されたCHとMCPが初期化されているか確認し、まだなら初期化する"""
        mcp_addr = self.mcp_addrs[mcp_idx]
        mcp_addr_8bit = mcp_addr << 1

        if channel not in self.states:
            self.states[channel] = {}

        if mcp_addr not in self.states[channel]:
            self.states[channel][mcp_addr] = {
                "a": 0xFF,
                "b": 0xFF,
                "initialized": False,
            }

        state = self.states[channel][mcp_addr]

        if not state["initialized"]:
            self._switch_mux(channel)

            # MCP23017 初期化 (全OFF -> 出力設定)
            try:
                # Active Low (OFF=1)
                self.smb.WriteRequest(mcp_addr_8bit, [0x12, 0xFF], 2)  # GPIOA
                self.smb.WriteRequest(mcp_addr_8bit, [0x13, 0xFF], 2)  # GPIOB
                # IODIR (0=Output)
                self.smb.WriteRequest(mcp_addr_8bit, [0x00, 0x00], 2)  # IODIRA
                self.smb.WriteRequest(mcp_addr_8bit, [0x01, 0x00], 2)  # IODIRB

                state["initialized"] = True
            except Exception as e:
                print(f"Failed to initialize MCP {mcp_idx} on CH {channel}: {e}")
                return False

        return True

    def set_relay(self, relay_number, turn_on, channel=0, mcp_index=0):
        """
        リレーを制御する

        :param relay_number: 0〜15 (PortA: 0-7, PortB: 8-15)
        :param turn_on: True(ON), False(OFF)
        :param channel: Mux Channel (0〜3)
        :param mcp_index: MCPのインデックス (0=0x20, 1=0x21, 2=0x22)
        """
        # --- 引数チェック ---
        if not (0 <= channel <= 3):
            print(f"Error: Invalid channel {channel}")
            return
        if not (0 <= mcp_index < len(self.mcp_addrs)):
            print(f"Error: Invalid MCP index {mcp_index}")
            return
        # 変更: 0〜15 の範囲チェック
        if not (0 <= relay_number <= 15):
            print(f"Error: Invalid relay number {relay_number} (Must be 0-15)")
            return

        # --- 初期化とMux切り替え ---
        if not self._ensure_mcp_initialized(channel, mcp_index):
            return
        self._switch_mux(channel)

        mcp_addr = self.mcp_addrs[mcp_index]
        mcp_addr_8bit = mcp_addr << 1
        current_state_dict = self.states[channel][mcp_addr]

        # --- リレー番号の計算 (変更点) ---
        # 0-7: Port A, 8-15: Port B
        is_port_a = relay_number < 8
        bit_index = relay_number % 8

        # Active Low (ON=0, OFF=1) のビット計算
        if is_port_a:
            reg = 0x12  # GPIOA
            current_val = current_state_dict["a"]
            if turn_on:
                new_val = current_val & ~(1 << bit_index)
            else:
                new_val = current_val | (1 << bit_index)

            self.smb.WriteRequest(mcp_addr_8bit, [reg, new_val], 2)
            current_state_dict["a"] = new_val
        else:
            reg = 0x13  # GPIOB
            current_val = current_state_dict["b"]
            if turn_on:
                new_val = current_val & ~(1 << bit_index)
            else:
                new_val = current_val | (1 << bit_index)

            self.smb.WriteRequest(mcp_addr_8bit, [reg, new_val], 2)
            current_state_dict["b"] = new_val


# ==========================================
# 使用例
# ==========================================
if __name__ == "__main__":
    controller = RelayController(mux_addr=0x70)

    if controller.open():
        try:
            print("--- Testing Start (0-15 mapping) ---")

            # テスト1: Port A の Pin 0 (Relay 0) を ON
            print("CH:1, MCP:0(0x20), Relay:0 (Port A-0) -> ON")
            controller.set_relay(0, True, channel=1, mcp_index=0)
            time.sleep(1.0)

            # テスト2: Port A の Pin 1 (Relay 1) を ON
            print("CH:1, MCP:0(0x20), Relay:1 (Port A-1) -> ON")
            controller.set_relay(1, True, channel=1, mcp_index=0)
            time.sleep(1.0)

            # テスト3: Port A の Pin 2 (Relay 2) を ON
            print("CH:1, MCP:0(0x20), Relay:2 (Port A-2) -> ON")
            controller.set_relay(2, True, channel=1, mcp_index=0)
            time.sleep(1.0)

            # テスト4: Port A の Pin 0 (Relay 0) を OFF
            print("CH:1, MCP:0(0x20), Relay:0 (Port A-0) -> OFF")
            controller.set_relay(0, False, channel=1, mcp_index=0)
            time.sleep(1.0)

            # テスト5: Port A の Pin 1 (Relay 1) を OFF
            print("CH:1, MCP:0(0x20), Relay:1 (Port A-1) -> OFF")
            controller.set_relay(1, False, channel=1, mcp_index=0)
            time.sleep(1.0)

            # テスト6: Port A の Pin 2 (Relay 2) を OFF
            print("CH:1, MCP:0(0x20), Relay:2 (Port A-2) -> OFF")
            controller.set_relay(2, False, channel=1, mcp_index=0)
            time.sleep(1.0)

            print("Done.")

        except KeyboardInterrupt:
            pass
        finally:
            controller.close()

# __END__
