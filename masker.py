from __future__ import division
import os, subprocess, csv, shutil, re, time, math
import pyelan.pyelan as pyelan

def readData(file="RobinTest.csv"):
    f = open(file, 'r')
    data = csv.DictReader(f)

    dataOut = {} #Initialize emptry dictionary
    for data in data:
        wordInstance = data["wordInstanceVideoPath"]
        wordInstance = os.path.basename(wordInstance)
        try:
            dataOut[wordInstance].append(data)
        except KeyError:
            dataOut[wordInstance] = [data]

    return dataOut

def chunks(l, n):
    """chunks a list into chunks of n length"""
    return [l[i:i+n] for i in range(0, len(l), n)]

def timeSpanFrameChanger(data, frames=1, shrink=False, fps=60000/1001.):
    """take a list of two, and adjusts the times by adding or subtracting frames on either side."""
    sign = frames
    if shrink == True:
        sign = sign*-1
    begin = int(round(data[0] - sign*(1/fps)*1000))
    end = int(round(data[1] + sign*(1/fps)*1000))
    out = [begin, end]
    return out

def timeSpanPercentageChanger(data, perc=0.5, shrink=True, fps=6000/1001.):
    """take a list of two, and adjusts the times by adding or subtracting a percentage on either side."""
    sign = 1
    if shrink == True:
        sign = sign*-1
    delta = data[1]-data[0]
    out = []
    out.append(int(round(data[0] - sign*(1-perc)*delta/2.)))
    out.append(int(round(data[1] + sign*(1-perc)*delta/2.)))
    return out

def spanChecker(data):
    """Check to make sure the spans given are well formed"""
    out = []
    for span in data:
        begin = span[0]
        end = span[1]
        # make sure no spans are before the beginning of the clip
        if begin < 0:
            begin = 0
        if end < 0:
            end = 0
        # make sure that no spans are negative
        if end-begin > 0:
            out.append([begin, end])
    return out

def imgSplicer(videoIn, wordDur, masks, outpath, slowDown=2, fpsin=59.94, maskImage="masker/masks/black852x480.jpg"):
    if masks != None:
        ### If there are mask durations to mask
        # change the spans
        print(masks)
        # masks = [timeSpanPercentageChanger(x, perc=0.75, shrink=True) for x in masks]
        masks = [timeSpanFrameChanger(x, frames=0, shrink=False, fps=30000/1001.) for x in masks]
        masks = spanChecker(masks)
        print(masks)
        # flatten the masks list
        nonMasks = [item for sublist in masks for item in sublist]
        nonMasks.append(0)
        nonMasks.append(wordDur[1]-wordDur[0])
        nonMasks = sorted(nonMasks)
        nonMasks = chunks(nonMasks, 2)
        # print(nonMasks)

        mspf = (1/fpsin)*1000

        #number of places in image files
        digits = 5

        imagePrefix = "tmp/image-"
        imageSuffix = ".png"

        nonMaskList = []
        for begin, end in nonMasks:
            begin = begin/mspf
            end = end/mspf

            # print(begin,end)

            beginFrame = int(round(begin))
            endFrame = int(round(end))

            # print(beginFrame,endFrame)

            #generate file names, add one to both to move from 0 indexed to 1 indexed. Add an additional one to the end frame to make it inclusive of the ending frame This needs to be checked against elan files
            nonMaskList.append([imagePrefix+str(n).zfill(digits)+imageSuffix for n in range(beginFrame+1, endFrame+1, 1)])
            # nonMaskList.append([imagePrefix+str(n).zfill(digits)+imageSuffix for n in range(beginFrame, endFrame, 1)])

        # remove the last frame of the list because it doesn't exist in the video.
        # imageList[-1].pop()

        imageList = [nonMaskList.pop(0)]
        for begin, end in masks:
            begin = begin/mspf
            end = end/mspf
            # print(begin, end)

            beginFrame = int(round(begin))
            endFrame = int(round(end))

            # print(beginFrame,endFrame)

            # for testing gives all of the frames
            # newimageList.append([imagePrefix+str(n).zfill(digits)+imageSuffix for n in range(beginFrame+1, endFrame+1, 1)])
            imageList.append([maskImage]*(endFrame-beginFrame))
            imageList.append(nonMaskList.pop(0))
        # flatten image list
        imageList = [item for sublist in imageList for item in sublist]

    elif masks == None:
        mspf = (1/fpsin)*1000

        #number of places in image files
        digits = 5

        imagePrefix = "tmp/image-"
        imageSuffix = ".png"


        begin = 0/mspf
        end = (wordDur[1]-wordDur[0])/mspf

        # print(begin,end)

        beginFrame = int(round(begin))
        endFrame = int(round(end))

        # print(beginFrame,endFrame)

        #generate file names, add one to both to move from 0 indexed to 1 indexed. Add an additional one to the end frame to make it inclusive of the ending frame This needs to be checked against elan files
        imageList = [imagePrefix+str(n).zfill(digits)+imageSuffix for n in range(beginFrame+1, endFrame+1, 1)]
        # imageList = [imagePrefix+str(n).zfill(digits)+imageSuffix for n in range(beginFrame, endFrame, 1)]


        # print(imageList)

        # remove the last frame of the list because it doesn't exist in the video.
        # imageList[-1].pop()


    n=1
    linkList = []
    for file in imageList:
        symLink = ''.join(["tmp/frame_",str(n).zfill(digits), ".png"])
        os.symlink(os.path.join("..", file), symLink)
        linkList.append(symLink)
        n += 1

    # print(linkList)

    ffmpegCatCmd = ['ffmpeg']

    fpsout = {2: 29.97,
              1: 59.94}

    ffmpegCatCmd.extend(['-r', str(fpsout[slowDown]), '-i', './tmp/frame_%05d.png'])

    ffmpegCatCmd.extend(['-pix_fmt', 'yuv420p', '-r', '29.97', '-y', outpath])

    # print(ffmpegCatCmd)
    output = subprocess.check_output(ffmpegCatCmd, universal_newlines=True)

    # remove the link files
    [os.remove(file) for file in linkList]

    return masks

def parser(data, fps=60000/1001., minFrames = 1, beforeAfter = [None,None]):
    """Parses out only the holds from a set of apogees given in data"""
    dataOut = {}

    mspf = 1000/fps
    for instance in data:
        wordBegin = int(data[instance][1]["wordBegin"])
        wordEnd = int(data[instance][1]["wordEnd"])
        timePoints = []
        for apogee in data[instance]:
            timePoints.append(int(apogee['beginTime']))
            timePoints.append(int(apogee['endTime']))

        timePoints = sorted(timePoints)

        wordBeginDiff = 0
        if beforeAfter[0] != None:
            # If the beginning trim is not none, trim the beggining, but only if there's enough to trim.
            # adjust the before value to be on a frame boundary.
            before = int(math.ceil(beforeAfter[0]/mspf)*mspf)
            newBegin = timePoints[0]-before
            if newBegin > wordBegin:
                wordBeginDiff = newBegin - wordBegin
                wordBegin = newBegin

        if beforeAfter[1] != None:
            # If the end trim is not none, trim the end, but only if there's enough to trim.
            # adjust the after value to be on a frame boundary.
            after = int(math.ceil(beforeAfter[1]/mspf)*mspf)
            newEnd = timePoints[-1]+after
            if newEnd < wordEnd:
                wordEnd = newEnd

        timePoints[:] = [x - wordBegin for x in timePoints]

        # if any two time points are less than (the duration of the number of) minimum frames, move the end until it hits a frame.
        minTime = (minFrames*1000)/(fps)

        timePointsMin = [timePoints[0]]
        for i in range(1,len(timePoints)-0):
            if timePoints[i] - timePoints[i-1] < minTime:
                timePointsMin.append(int(round(timePoints[i-1]+minTime)))
            else:
                timePointsMin.append(timePoints[i])

        for i in range(1,len(timePointsMin)-0):
            if timePointsMin[i] - timePointsMin[i-1] < minTime-1:
                print("The holds and transitions are such that expanding all spans to the minimum time makes other spans less than the minnimum.")
                print(data[instance][1]["wordInstanceVideoID"])

        timePoints = timePointsMin

        holds = chunks(timePoints, 2)

        timePoints = sorted(timePoints)[1:-1]
        transitions = chunks(timePoints, 2)


        word = data[instance][1]["word"]
        dataOut[instance] = ((wordBegin, wordEnd), word, holds, transitions, wordBeginDiff)
    return dataOut


def processor(dataIn, outdir, slowDown=2, maskImage="masker/masks/green852x480.jpg"):
    for videoIn in dataIn:
        fps = 59.94

        # setup temp directories
        if os.path.exists("tmp"):
            shutil.rmtree("tmp")
        os.makedirs("tmp")

        if not os.path.exists(outdir):
            os.makedirs(outdir)
        #
        # extract frames of the video.
        # ffmpeg -i originalVideos/730.mp4 -q:v 1 -r 59.94 -f image2 testImg/image-%5d.png png is much bigger, but seems to be more faithful.
        output = subprocess.check_output(["ffmpeg", "-i", "originalVideos/"+videoIn, "-q:v", "1", "-r", str(fps), "-ss", str(dataIn[videoIn][4]/1000.), "-f", "image2", "-y", "tmp/image-%5d.png"])

        if not os.path.exists(os.path.join(outdir,'holdsOnly')):
            os.makedirs(os.path.join(outdir,'holdsOnly'))

        transMaskedfile = os.path.join(outdir,'holdsOnly','stim'+videoIn)
        transMasked = imgSplicer(videoIn, wordDur=dataIn[videoIn][0], masks=dataIn[videoIn][3], outpath=transMaskedfile, slowDown=slowDown, fpsin=fps, maskImage=maskImage)

        if not os.path.exists(os.path.join(outdir,'transOnly')):
            os.makedirs(os.path.join(outdir,'transOnly'))

        holdsMaskedfile = os.path.join(outdir,'transOnly','stim'+videoIn)
        holdsMasked = imgSplicer(videoIn, wordDur=dataIn[videoIn][0], masks=dataIn[videoIn][2], outpath=holdsMaskedfile, slowDown=slowDown, maskImage=maskImage)

        if not os.path.exists(os.path.join(outdir,'allClear')):
            os.makedirs(os.path.join(outdir,'allClear'))

        clearfile = os.path.join(outdir,'allClear','stim'+videoIn)
        imgSplicer(videoIn, wordDur=dataIn[videoIn][0], masks=None, outpath=clearfile, slowDown=slowDown, maskImage=maskImage)

        if not os.path.exists(os.path.join(outdir,'elanFiles')):
            os.makedirs(os.path.join(outdir,'elanFiles'))

        saveDir = os.path.join(outdir, "elanFiles")
        basename = os.path.splitext(videoIn)[0]
        media = [clearfile, holdsMaskedfile, transMaskedfile]

        if slowDown == 2:
            holdMasksTier = pyelan.tier("hold masks", [pyelan.annotation(begin=beg*slowDown, end=end*slowDown, value="") for beg, end in holdsMasked] )
            transMasksTier = pyelan.tier("trans masks", [pyelan.annotation(begin=beg*slowDown, end=end*slowDown, value="") for beg, end in transMasked])
            holdsAnnos = [pyelan.annotation(begin=beg*slowDown, end=end*slowDown, value="") for beg, end in dataIn[videoIn][2]]
        elif slowDown == 1:
            adjust = int(round((1000/59.94)*4))
            # add one frame('s worth of miliseconds) to each of the annotations to make up for adding one above.
            holdMasksTier = pyelan.tier("hold masks", [pyelan.annotation(begin=(beg+adjust)*slowDown, end=(end+adjust)*slowDown, value="") for beg, end in holdsMasked] )
            transMasksTier = pyelan.tier("trans masks", [pyelan.annotation(begin=(beg+adjust)*slowDown, end=(end+adjust)*slowDown, value="") for beg, end in transMasked])
            holdsAnnos = [pyelan.annotation(begin=(beg+adjust)*slowDown, end=(end+adjust)*slowDown, value="") for beg, end in dataIn[videoIn][2]]

        for n in range(0, len(holdsAnnos)):
            holdsAnnos[n].value = dataIn[videoIn][1][n]

        holdsTier = pyelan.tier("holds", holdsAnnos)

        tiers = [holdsTier, holdMasksTier, transMasksTier]

        allTiers = pyelan.tierSet(media=media, tiers=tiers)

        elanOut = os.path.join(saveDir,'.'.join([basename,"eaf"]))

        out = pyelan.tierSet.elanOut(allTiers, dest=elanOut)

        out.write(elanOut)

        shutil.rmtree("tmp")




d = readData(file = "ritaAndRobinApogeesCleaned.csv")

words = parser(d, fps=30000/1001., minFrames = 1, beforeAfter = [1000,250])
# {"730.mp4": words["730.mp4"]}
# processor(words, outdir="greenRegular", slowDown=1, maskImage="masker/masks/green852x480.png")

processor(words, outdir="blackRegular", slowDown=1, maskImage="masker/masks/black852x480.png")

processor(words, outdir="grayRegular", slowDown=1, maskImage="masker/masks/50gray852x480.png")
