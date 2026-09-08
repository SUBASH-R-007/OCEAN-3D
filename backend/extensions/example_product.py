"""Default demonstration product contract. Does not execute/train an ML model."""
from ..plugins import register_variable, register_product

PLUGIN={'api_version':1,'id':'example-ml-output','version':'1.0.0','label':'Synthetic ML-output contract example'}


def register():
    register_variable(dict(id='ml_temperature_anomaly',label='Example temperature anomaly',unit='°C',
        canonical_unit='degree_Celsius',standard=None,aliases=['ml_temperature_anomaly'],
        unit_aliases=['degree_Celsius'],range=[-2,2]))
    register_product(dict(id='ml-anomaly-example',label='Synthetic ML-output contract',kind='machine-learning',
        version='1.0.0',outputs=['ml_temperature_anomaly'],
        method='Analytic fixture exercising the externally computed ML-output interface. No trained model is executed.',
        limitations='Synthetic integration example; not an ML prediction, hazard advisory or validation of predictive skill.'))
