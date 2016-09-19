'''
BLM Framework by Yamanishi and Beakley
'''

import numpy as np
import matplotlib.pyplot as plt
import json
from collections import defaultdict
from sklearn.cross_validation import KFold
from sklearn.cross_validation import StratifiedKFold
from sklearn import svm
from sklearn.metrics import precision_recall_curve
from sklearn.metrics import roc_auc_score
from sklearn.metrics import roc_curve, auc
from sklearn.metrics import average_precision_score
from sklearn.metrics import accuracy_score
from sklearn.metrics import recall_score
from sklearn.metrics import precision_score
from scipy import interp
from scoop import futures as fu

class BLM:
    dataX = []; dataY = []; nData = 0
    proteinSimMat = None; proteinSimMatMeta = None
    drugSimMat = None; drugSimMatMeta = None

    def __init__(self, fpath, drugSimMatFpath, proteinSimMatFpath):
        self._loadBinding(fpath)
        self._loadSimMat(drugSimMatFpath, proteinSimMatFpath)

    def eval(self, outDir):
        nFolds = self.nData
        kfList = KFold(self.nData, n_folds=nFolds, shuffle=True) 

        # nFolds = 10
        # kfList = StratifiedKFold(self.dataY, n_folds=nFolds, shuffle=True)

        #
        kfResult = fu.map(self._evalPerFold, kfList, [self.dataX]*nFolds, [self.dataY]*nFolds)

        # Combine the results from across all folds
        predResults = defaultdict(list)
        predOfDrugSet = []
        predOfProteinSet = []
        predOfDrugAndProteinSet = []

        for result in kfResult:
            yPredOfDrugSet, yPredOfProteinSet, yTest = result

            for i, y in enumerate(yTest):
                yd = yPredOfDrugSet[i]
                yp = yPredOfProteinSet[i]

                if yd!=None:
                    predResults['ofDrugSet'].append((yd,y))

                if yp!=None:
                    predResults['ofProteinSet'].append((yp,y))

                if yd!=None and yp!=None:
                    predResults['ofDrugAndProteinSet'].append( (max(yd,yp),y) )

        # Compute ROC curve and PR curve
        perf = dict.fromkeys(predResults.keys())
        perf2 = dict.fromkeys(predResults.keys())

        for key, value in predResults.iteritems():
            yPred = [v[0] for v in value]
            yTest = [v[1] for v in value]

            fpr, tpr, _ = roc_curve(yTest, yPred)
            rocAUC = roc_auc_score(yTest, yPred)

            precision, recall, _ = precision_recall_curve(yTest, yPred)
            prAUC = average_precision_score(yTest, yPred, average='micro')

            lineType = None
            if key=='ofDrugSet':
                lineType = 'r-'
            elif key=='ofProteinSet':
                lineType = 'b--'
            elif key=='ofDrugAndProteinSet':
                lineType = 'g:'
            else:
                lineType = 'k-.'

            perf[key] = {'fpr': fpr, 'tpr': tpr, 'rocAUC': rocAUC,
                         'precision': precision, 'recall': recall, 'prAUC': prAUC,
                         'lineType': lineType}
            perf2[key] = {'rocAUC': rocAUC,'prAUC': prAUC}

        with open(outDir+'/perf.json', 'w') as fp:
            json.dump(perf2, fp, indent=2, sort_keys=True)

        plt.clf()
        plt.figure()
        for key, locPerf in perf.iteritems():
            plt.plot(locPerf['fpr'], locPerf['tpr'], locPerf['lineType'],
                    label=key+' (area = %0.2f)' % locPerf['rocAUC'], lw=2)
        plt.xlim([-0.05, 1.05])
        plt.ylim([-0.05, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver operating characteristic (ROC) Curve')
        plt.legend(loc="lower right")
        plt.savefig(outDir+'/roc_curve.png', bbox_inches='tight')

        plt.clf()
        plt.figure()
        for key, locPerf in perf.iteritems():
            plt.plot(locPerf['recall'], locPerf['precision'], locPerf['lineType'],
                    label= key+' (area = %0.2f)' % locPerf['prAUC'], lw=2)
        plt.ylim([-0.05, 1.05])
        plt.xlim([-0.05, 1.05])
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall Curve')
        plt.legend(loc="lower left")
        plt.savefig(outDir+'/pr_curve.png', bbox_inches='tight')

    def _evalPerFold(self, kf, dataX, dataY):
        trIdxList, testIdxList = kf
        xTest = [dataX[i] for i in testIdxList]
        yTest = [dataY[i] for i in testIdxList]

        xTr = [dataX[i] for i in trIdxList]
        yTr = [dataY[i] for i in trIdxList]

        #
        yPredOfProteinSet = self._predict('usingProteinSetAsTrainingData', xTest, xTr, yTr)
        yPredOfDrugSet = self._predict('usingDrugSetAsTrainingData', xTest, xTr, yTr)
        assert(len(yPredOfDrugSet)==len(yPredOfProteinSet)==len(yTest))

        return (yPredOfDrugSet, yPredOfProteinSet, yTest)

    def _predict(self, type, xTest, xTr, yTr):
        # get _local_ (w.r.t. testData) training data
        xTrLocal = []
        yTrLocal = []

        simMat = None
        simMatMeta = None
        
        refIdx = None
        if type=='usingDrugSetAsTrainingData':
            refIdx = 1 # ref is protein in xTest
            simMat = self.drugSimMat
            simMatMeta = self.drugSimMatMeta
        elif type=='usingProteinSetAsTrainingData':
            refIdx = 0 # ref is drug in xTest
            simMat = self.proteinSimMat
            simMatMeta = self.proteinSimMatMeta
        else:
            assert(False)

        refList = [d[refIdx] for d in xTest] 
        for idx,d in enumerate(xTr):
            if (d[refIdx] in refList):
                xTrLocal.append(d)
                yTrLocal.append( yTr[idx] )

        #
        yPred = None
        if (len(set(yTrLocal))==2): # as for binary clf
            # Use only either drug or protein only from x(drug,protein)
            xTrLocal = [i[int(not refIdx)] for i in xTrLocal]
            xTestLocal = [i[int(not refIdx)] for i in xTest]

            #
            gramTr = self._makeGram(xTrLocal, xTrLocal, simMat, simMatMeta)
            gramTest = self._makeGram(xTestLocal,xTrLocal, simMat, simMatMeta)

            #
            clf = svm.SVC(kernel='precomputed')
            clf.fit(gramTr,yTrLocal)

            yPred = clf.predict(gramTest)
        else:
            yPred = [None]*len(xTest)
            
        return yPred

    def _loadBinding(self, fpath):
        content = []
        with open(fpath) as f:
            content = f.readlines()

        drugList = []
        proteinList = []
        drugProteinDict = defaultdict(list)
        for c in content:
            tmp = [i.strip() for i in c.split()]
            
            proteinList.append(tmp[0])
            drugList.append(tmp[1])

            drugProteinDict[tmp[1]].append( tmp[0] )

        drugList = list(set(drugList))
        proteinList = list(set(proteinList))
        assert(len(drugList)==len(drugProteinDict))

        self.dataX = [(i,j) for i in drugList for j in proteinList]
        for x in self.dataX:
            targetProteinList = drugProteinDict[ x[0] ]
            self.dataY.append(int( x[1] in targetProteinList ))

        assert(len(self.dataX)==len(self.dataY))
        self.nData = len(self.dataX)

    def _loadSimMat(self, drugSimMatFpath, proteinSimMatFpath):
        self.proteinSimMatMeta, self.proteinSimMat = self._readSimMat(proteinSimMatFpath)
        self.drugSimMatMeta, self.drugSimMat = self._readSimMat(drugSimMatFpath)
        
    def _readSimMat(self, fpath):
        with open(fpath) as f:
            content = f.readlines()

        simMatMeta = []
        simMat = None
        for idx,c in enumerate(content):
            if idx==0:
                simMatMeta = [i.strip() for i in c.split()]
                n = len(simMatMeta)
                simMat = np.zeros((n,n),dtype=float)
            else:
                valStr = [i.strip() for i in c.split()]
                assert(valStr[0]==simMatMeta[idx-1])
                del valStr[0]
                i = idx - 1
                for j,v in enumerate(valStr):
                    simMat[i][j] = float(v)

        return (simMatMeta, simMat)

    def _makeGram(self, X1, X2, simMat, meta):
        shape = (len(X1),len(X2))
        gram = np.zeros(shape)

        for i, x1 in enumerate(X1):
            for j, x2 in enumerate(X2):
                x1 = x1.replace(':','')
                x2 = x2.replace(':','')
                
                ii = meta.index(x1)
                jj = meta.index(x2)
                
                gram[i][j] = simMat[ii][jj]
                assert(gram[i][j] >= 0)

        return gram
