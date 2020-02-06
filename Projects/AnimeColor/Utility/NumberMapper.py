def translate(value, leftMin, leftMax, rightMin, rightMax):
    # Figure out how 'wide' each range is
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin

    # Convert the left range into a 0-1 range (float)
    valueScaled = float(value - leftMin) / float(leftSpan)

    # Convert the 0-1 range into a value in the right range.
    return  rightMin + (valueScaled * rightSpan)

while(True):
    print('insert Hue')
    hue=float(input())
    print('insert Saturation')
    saturation=float(input())
    print('insert Value')
    value=float(input())
    print('HSV')
    print(translate(hue, 0, 360, 0, 255))
    print(translate(saturation, 0, 100, 0, 255))
    print(translate(value, 0, 100, 0, 255))