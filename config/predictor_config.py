# predictor_config.py

## Individual predictors
rndlyConfig = dict(name='rndly',weight=0.5,batchSize=1)
kronRLSConfig = dict(name='kronrls',weight=0.6,
                     batchSize=1,maxTrainingDataSize=100,
                     gamma=1.0,threshold=0.5,
                     alphaCompoundKernel=0.5,alphaProteinKernel=0.5,
                     kernelBandwidth=1.0)
blmniiConfig = dict(name='blmnii',weight=0.6,batchSize=1,
                    maxTrainingDataSize=1000)

## Common params
predictorConfig = dict()
predictorConfig['maxElapsedTime'] = 5 # in seconds
predictorConfig['methods'] = [rndlyConfig,kronRLSConfig]
predictorConfig['trainingDataSources'] = ['drugbank.ca']
