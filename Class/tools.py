class Tools():
    
    def getAvrg(self,row):
        average = 0
        for ms in row:
            if ms == "timed out": continue
            average += float(ms)
        if average == 0: return 65000
        return average / len(row)