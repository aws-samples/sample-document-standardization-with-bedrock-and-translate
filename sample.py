def process_education_column(df):
    print(f"Type of df: {type(df)}")

    # Create a new column based on whether 'high' is in the 'education' column
    df = df.str.contains('high', case=False, na=False).map({True: 'Yes', False: 'No'})
    
    return df