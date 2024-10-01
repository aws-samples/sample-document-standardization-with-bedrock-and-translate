

def compute_vif(df, threshold):

    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from statsmodels.tools.tools import add_constant
    import pandas as pd
    import numpy as np
    from pyspark.sql.types import StringType, FloatType,LongType
    from pyspark import SparkContext, SQLContext
    from pyspark.sql.functions import lit
    from pyspark.sql import SQLContext
    sc = SparkContext.getOrCreate()
    sqlContext = SQLContext(sc)
    from pyspark.sql.types import IntegerType, Row
    import pyspark.sql.functions as F
    from pyspark.sql.window import Window

    considered_features=[f.name for f in df.schema.fields if isinstance(f.dataType, (FloatType,LongType))]
    X=df[considered_features]
    X=X.dropna()
    X=X.withColumn('intercept', lit(1).cast('float'))
    X.schema['intercept'].nullable = True
    col = map(lambda x : Row(x), X.schema.names)
    vif = sqlContext.createDataFrame(col,["Variable"])
    array=np.array(X.select('*').collect())
    vif_values= [variance_inflation_factor(array, i) for i in range(len(X.columns))]  
    w=Window().orderBy("VIF")
    vif = vif.withColumn("VIF",  F.array(* [F.lit(x) for x in vif_values] ))\
    .withColumn("rownum", F.row_number().over(w))\
    .withColumn("VIF", F.expr("""element_at(VIF,rownum)""")).drop("rownum")    
    vif = vif.filter(vif['Variable']!='intercept')
    vif=vif.sort('VIF',ascending = False)
    vif.show()
    vif=vif.where(vif.VIF>threshold)
    drop_clm_names=vif.select(F.collect_list('Variable')).first()[0]
    df=df.drop(*drop_clm_names)
    return df


