# importing the required module
import matplotlib.pyplot as plt

poses = {'s3': [90, 105, 45, 45, 90, 0, 0, 0, 0, 0, 0, 90, 90, 90, 75, 90], 's4': [90, 116, 60, 45, 90, 0, 0, 0, 0, 0, 0, 90, 90, 90, 70, 70], 's5': [75, 116, 60, 45, 90, 0, 0, 0, 0, 0, 0, 90, 90, 90, 80, 70], 's6': [75, 116, 60, 45, 90, 0, 0, 0, 0, 0, 0, 90, 140, 140, 62, 90], 's7': [75, 116, 60, 80, 90, 0, 0, 0, 0, 0, 0, 90, 140, 140, 80, 90], 's8': [90, 116, 60, 80, 90, 0, 0, 0, 0, 0, 0, 90, 140, 140, 80, 90], 's9': [110, 120, 90, 90, 90, 0, 0, 0, 0, 0, 0, 90, 135, 120, 64, 90], 's10': [110, 110, 90, 90, 90, 0, 0, 0, 0, 0, 0, 90, 135, 120, 64, 105], 's11': [110, 120, 40, 40, 90, 0, 0, 0, 0, 0, 0, 90, 135, 120, 64, 105], 's12': [110, 100, 40, 40, 90, 0, 0, 0, 0, 0, 0, 90, 100, 120, 64, 105], 's13': [90, 100, 40, 40, 90, 0, 0, 0, 0, 0, 0, 90, 100, 120, 64, 90]}
  
# x axis values
x = [1,2,3]
# corresponding y axis values
y = [2,4,1]
  
t = [1,2,3,4,5,6,7,8,9,10,11]

joints = {"ankleLx": [], "ankleLy": [], "kneeL": [], "hipLy": [], "hipLz": [], "ankleRx": [], "ankleRy": [], "kneeR": [], "hipRy": [], "hipRz": []}

for s in poses:
    joints["ankleLx"].append(poses[s][0])
    joints["ankleLy"].append(poses[s][1])
    joints["kneeL"].append(poses[s][2])
    joints["hipLy"].append(poses[s][3])
    joints["hipLz"].append(poses[s][4])
    joints["ankleRx"].append(poses[s][15])
    joints["ankleRy"].append(poses[s][14])
    joints["kneeR"].append(poses[s][13])
    joints["hipRy"].append(poses[s][12])
    joints["hipRz"].append(poses[s][1])
    
# plotting the points
#for j in joints:
    #if(j != "hipLz" and j != "hipRz"):
        #plt.plot(t, joints[j], label = j)
plt.plot(t, joints["ankleLx"], label = "ankleLx", color ="red") 
plt.plot(t, joints["ankleLy"], label = "ankleLy", color ="green") 
plt.plot(t, joints["kneeL"], label = "kneeL", color ="blue") 
plt.plot(t, joints["hipLy"], label = "hipLy", color ="orange") 
plt.plot(t, joints["ankleRx"], label = "ankleRx", color ="red", linestyle='dashed') 
plt.plot(t, joints["ankleRy"], label = "ankleRy", color ="green", linestyle='dashed') 
plt.plot(t, joints["kneeR"], label = "kneeR", color ="blue", linestyle='dashed') 
plt.plot(t, joints["hipRy"], label = "hipRy", color ="orange", linestyle='dashed') 

# naming the x axis
plt.xlabel('Pose')
# naming the y axis
plt.ylabel('Angle')
  
# giving a title to my graph
plt.title('Biped walk joint angles')

plt.legend()
  
# function to show the plot
plt.show()