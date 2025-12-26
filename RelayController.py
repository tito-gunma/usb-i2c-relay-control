#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import SLABHIDtoSMBUS as hid
import ctypes as ct
import time

class RelayController:
    def __init__(self, mux_ch=1, mcp_addr=0x20):
        self.mux_ch = mux_ch
        self.mcp_addr_8bit = mcp_addr << 1
        self.mux_addr_8bit = 0x70 << 1
        
        self.smb = hid.HidSmbusDevice()
        self._lib = hid._DLL
        self._setup_lib_types()
        
        # 現在のリレー状態を保持するキャッシュ (A=Low byte, B=High byte)
        self.current_state_a = 0xFF # 初期値 OFF (Active Low)
        self.current_state_b = 0xFF 
        
        self.is_connected = False

    def _setup_lib_types(self):
        """DLL関数の型定義修正"""
        self._lib.HidSmbus_GetReadResponse.argtypes = [
            ct.c_void_p, ct.POINTER(ct.c_ubyte), ct.c_char_p, ct.c_ubyte, ct.POINTER(ct.c_ubyte)
        ]
        self._lib.HidSmbus_GetReadResponse.restype = ct.c_int

    def open(self):
        """デバイス接続と初期化"""
        try:
            self.smb.Open(0)
            self.is_connected = True
            
            # 手動読み取りモードに設定 (安定性重視)
            self.smb.SetTimeouts(1000)
            self.smb.SetSmbusConfig(100000, 0x02, False, 1000, 1000, False, 3)
            
            # Mux 設定
            self.smb.WriteRequest(self.mux_addr_8bit, [1 << self.mux_ch], 1)
            time.sleep(0.05)
            
            # MCP23017 初期化 (全OFF -> 出力設定)
            # GPA/GPB を 0xFF (OFF) に
            self.smb.WriteRequest(self.mcp_addr_8bit, [0x12, 0xFF], 2)
            self.smb.WriteRequest(self.mcp_addr_8bit, [0x13, 0xFF], 2)
            # IODIRA/B を 0x00 (Output) に
            self.smb.WriteRequest(self.mcp_addr_8bit, [0x00, 0x00], 2)
            self.smb.WriteRequest(self.mcp_addr_8bit, [0x01, 0x00], 2)
            time.sleep(0.05)
            
            print("RelayBoard initialized successfully.")
            return True
            
        except Exception as e:
            print(f"Initialization Failed: {e}")
            self.close()
            return False

    def close(self):
        """切断処理"""
        if self.is_connected and self.smb.IsOpened():
            # 安全のため全OFFにする (必要なければコメントアウト)
            self.write_port_a(0xFF)
            self.write_port_b(0xFF)
            self.smb.Close()
            self.is_connected = False
            print("RelayBoard connection closed.")

    def write_port_a(self, value):
        """Port A (Relay 1-8) に直接書き込む"""
        self.smb.WriteRequest(self.mcp_addr_8bit, [0x12, value], 2)
        self.current_state_a = value

    def write_port_b(self, value):
        """Port B (Relay 9-16) に直接書き込む"""
        self.smb.WriteRequest(self.mcp_addr_8bit, [0x13, value], 2)
        self.current_state_b = value

    def set_relay(self, relay_number, turn_on):
        """
        個別のリレーを制御する
        relay_number: 1〜16
        turn_on: True(ON), False(OFF)
        """
        if not (1 <= relay_number <= 16):
            print(f"Error: Invalid relay number {relay_number}")
            return

        # リレー番号をポートとビットに変換 (Active Low: ON=0, OFF=1)
        # Port A: 1-8, Port B: 9-16
        is_port_a = (relay_number <= 8)
        bit_index = (relay_number - 1) % 8
        
        # Active Low なので、ONならビットを下げる(0)、OFFなら上げる(1)
        target_val = 0 if turn_on else 1
        
        if is_port_a:
            current = self.current_state_a
            # ビット操作
            if turn_on:
                new_val = current & ~(1 << bit_index) # ビットを0にする
            else:
                new_val = current | (1 << bit_index)  # ビットを1にする
            
            self.write_port_a(new_val)
        else:
            current = self.current_state_b
            if turn_on:
                new_val = current & ~(1 << bit_index)
            else:
                new_val = current | (1 << bit_index)
            
            self.write_port_b(new_val)

# ==========================================
# 使用例
# ==========================================
if __name__ == "__main__":
    controller = RelayController()
    
    if controller.open():
        try:
            print("Testing Relay 1 (Click!)...")
            controller.set_relay(1, True)  # ON
            time.sleep(1.0)
            controller.set_relay(1, False) # OFF
            time.sleep(0.5)

            print("Testing Relay 9 (Click!)...")
            controller.set_relay(9, True)  # ON (Port B)
            time.sleep(1.0)
            controller.set_relay(9, False) # OFF
            
            print("Done.")
            
        except KeyboardInterrupt:
            pass
        finally:
            controller.close()

# __END__
