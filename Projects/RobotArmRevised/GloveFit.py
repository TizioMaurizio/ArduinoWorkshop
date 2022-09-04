"""
import matplotlib.pyplot as plt
import numpy as np


offset = -348
realX = np.array([0, 30, 45, 60, 75, 90])
realY = np.array([348, 449, 507, 532, 535, 540])

for i in range(len(realY)):
    realY[i] = realY[i] + offset
    realY[i] = realY[i]

for i in range(7):
    x = i*10
    y = x**3
    #print(x)
    #print(0.01*y)


#plt.plot(realX, realY)
#plt.plot(realX, np.sqrt(realX))


from numpy.polynomial import polynomial as P
import random


np.random.seed(123)
x = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7 ,8] # x "data": [-1, -0.96, ..., 0.96, 1]
y = []
for i in range(len(x)):
    y.append(x[i]**2)
    
print(x)
print(y)
plt.plot(x, y, label = "real")
for i in range(len(x)):
    y[i] = y[i] + random.uniform(0, 1)
plt.plot(x, y, label = "noise")

c, stats = P.polyfit(x,y,0,full=True)
c # c[0], c[2] should be approx. 0, c[1] approx. -1, c[3] approx. 1


estY = [] 

for i in range(len(x)):
    val = 0
    for j in range(len(c)):
        val = val + c[j]*x[i]**(len(c)-j)
    estY.append(val)

print(estY)
print(c)
plt.plot(x, estY,  label = "estimated")
plt.legend()
# function to show the plot
plt.show()"""
         

import matplotlib.pyplot as plt
import numpy as np

x = [542, 541, 540, 539, 538, 536, 535, 534, 532, 531, 530, 528, 527,
       524, 522, 518, 514, 511, 507, 502, 496, 490, 484, 478, 471, 464,
       457, 450, 444, 437, 428, 418, 406, 401, 392, 390, 388]
y = [0,2,3,5,6,7,8,10,11,13,14,15,17,19,21,23,24,25,26,28,30,31,31,33
,34,35,37,38,39,41,42,43,44,45,47,48,50]

    
fit = np.polyfit(x,y,3)
#plot the fitted function
xfit = np.linspace(200,max(x),100)
yfit = np.polyval(fit,xfit)
print(fit)
plt.plot(xfit,yfit, label = "estimated")
plt.plot(x,y, label = "real") 
plt.legend()
plt.show()        
                
