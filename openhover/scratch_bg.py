from PIL import Image

def remove_background():
    img = Image.open('d:/helves/openhover/assets/bubble-icon.jpg')
    img = img.convert('RGBA')
    datas = img.getdata()
    
    newData = []
    # The background is dark. Let's make anything close to black transparent.
    # We might need to handle anti-aliasing, so anything darker than a threshold gets partial transparency or we just make anything dark transparent.
    # Looking at the image, it's a white icon on a dark background.
    for item in datas:
        # item is (R, G, B, A)
        # If it's dark, make it transparent
        brightness = sum(item[0:3]) / 3
        if brightness < 100:
            newData.append((item[0], item[1], item[2], 0))
        else:
            newData.append((item[0], item[1], item[2], item[3]))
            
    img.putdata(newData)
    img.save('d:/helves/openhover/assets/bubble-icon.png', 'PNG')

remove_background()
