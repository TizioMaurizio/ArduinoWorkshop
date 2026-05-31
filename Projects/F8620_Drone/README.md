# F8620 Drone — Flight Controller

Custom firmware for the F8620 8.6 mm coreless quadcopter kit on Arduino Nano. Drives 4 brushed motors via MOSFETs and accepts either C3-7-RX 2.4 GHz receiver input or serial commands (`T<thr> Y<yaw> P<pit> R<roll>`).

Entry: `F8620_Drone.ino`. Modules: `mixer.h`, `receiver.h`, `config.h`.
