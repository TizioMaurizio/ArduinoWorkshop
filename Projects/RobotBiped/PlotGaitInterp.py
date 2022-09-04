# importing the required module
import matplotlib.pyplot as plt
import numpy as np

from scipy import interpolate

interp_type = "linear"

poses = {'s3': [90, 105, 45, 45, 90, 0, 0, 0, 0, 0, 0, 90, 90, 90, 75, 90], 's4': [90, 116, 60, 45, 90, 0, 0, 0, 0, 0, 0, 90, 90, 90, 70, 70], 's5': [75, 116, 60, 45, 90, 0, 0, 0, 0, 0, 0, 90, 90, 90, 80, 70], 's6': [75, 116, 60, 45, 90, 0, 0, 0, 0, 0, 0, 90, 140, 140, 62, 90], 's7': [75, 116, 60, 80, 90, 0, 0, 0, 0, 0, 0, 90, 140, 140, 80, 90], 's8': [90, 116, 60, 80, 90, 0, 0, 0, 0, 0, 0, 90, 140, 140, 80, 90], 's9': [110, 120, 90, 90, 90, 0, 0, 0, 0, 0, 0, 90, 135, 120, 64, 90], 's10': [110, 110, 90, 90, 90, 0, 0, 0, 0, 0, 0, 90, 135, 120, 64, 105], 's11': [110, 120, 40, 40, 90, 0, 0, 0, 0, 0, 0, 90, 135, 120, 64, 105], 's12': [110, 100, 40, 40, 90, 0, 0, 0, 0, 0, 0, 90, 100, 120, 64, 105], 's13': [90, 100, 40, 40, 90, 0, 0, 0, 0, 0, 0, 90, 100, 120, 64, 90]}
  
# x axis values
x = [1,2,3]
# corresponding y axis values
y = [2,4,1]
  
t = [1,2,3,4,5,6,7,8,9,10,11]

joints = {"ankLx": [], "ankLy": [], "kneeL": [], "hipLy": [], "hipLz": [],
          "hipRz": [], "hipRy": [], "kneeR": [], "ankRy": [], "ankRx": []}

for s in poses:
    joints["ankLx"].append(poses[s][0])
    joints["ankLy"].append(poses[s][1])
    joints["kneeL"].append(poses[s][2])
    joints["hipLy"].append(poses[s][3])
    joints["hipLz"].append(poses[s][4])
    joints["ankRx"].append(poses[s][15])
    joints["ankRy"].append(poses[s][14])
    joints["kneeR"].append(poses[s][13])
    joints["hipRy"].append(poses[s][12])
    joints["hipRz"].append(poses[s][11])

off_t = int(np.mean(t))
print(off_t)

for key_l in joints.keys():
    if "L" in key_l:
        key_r = key_l.replace("L", "R")
        joints[key_r] = list(180 - np.roll(joints[key_l], off_t))

t_int = np.linspace(np.min(t), np.max(t), len(t) * 10)
x = t


orig_keys = list(joints.keys())
joints_int = {}
for key in orig_keys:
    y = joints[key]
    f = interpolate.interp1d(x, y, kind=interp_type)
    y_int = f(t_int)
    y_int = np.round(y_int).astype(int)
    joints_int[key + "_int"] = list(y_int)

# print(joints_int)

s_dict = {}
for i in range(len(t_int)):
    ll = []
    for k, v in joints_int.items():
        ll.append(int(v[i]))
        if len(ll) == 5:
            ll.append(0)
            ll.append(0)
            ll.append(0)
            ll.append(0)
            ll.append(0)
            ll.append(0)
    s_dict[f"s{i}"] = ll

import json

with open("narrowGaitV2_interp.json", "w") as fp:
    fp.write(json.dumps(s_dict))
    fp.write("\n")

#print(s_dict)

# plotting the points 
#for j in joints:
    #if(j != "hipLz" and j != "hipRz"):
        #plt.plot(t, joints[j], label = j)
plt.plot(t_int, joints_int["ankLx_int"], label = "ankLx", color ="red")
plt.plot(t_int, joints_int["ankLy_int"], label = "ankLy", color ="green") 
plt.plot(t_int, joints_int["kneeL_int"], label = "kneeL", color ="blue") 
plt.plot(t_int, joints_int["hipLy_int"], label = "hipLy", color ="orange") 
plt.plot(t_int, joints_int["ankRx_int"], label = "ankRx", color ="red", linestyle='dashed') 
plt.plot(t_int, joints_int["ankRy_int"], label = "ankRy", color ="green", linestyle='dashed') 
plt.plot(t_int, joints_int["kneeR_int"], label = "kneeR", color ="blue", linestyle='dashed') 
plt.plot(t_int, joints_int["hipRy_int"], label = "hipRy", color ="orange", linestyle='dashed') 

# naming the x axis
plt.xlabel('Pose')
# naming the y axis
plt.ylabel('Angle')
  
# giving a title to my graph
plt.title('Biped walk joint angles')

plt.legend()
  
# function to show the plot
plt.show()
