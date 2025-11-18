import os
import json
from xgboost import XGBRegressor
from xgboost import plot_importance
from sklearn.metrics import mean_squared_error
import numpy as np
from air_quality_backfill_cardiff import get_hopsworks_project, get_sensor_metadata
from util import plot_air_quality_forecast


def create_or_get_feature_view(fs):
    fg_aq = fs.get_feature_group(name='air_quality', version=1)
    fg_weather = fs.get_feature_group(name='weather', version=1)
    selected_features = fg_aq.select(['pm25', 'date']).join(fg_weather.select_features(), on=['city'])

    feature_view = fs.get_or_create_feature_view(
        name='air_quality_fv',
        description="weather features with air quality as the target",
        version=1,
        labels=['pm25'],
        query=selected_features,
    )
    return feature_view


def get_train_test_data(fv):
    # This will read the joined data from Hopsworks and split into train/test
    x_train, x_test, y_train, y_test = fv.train_test_split(test_size=0.2)
    print("Training data shapes:")
    print(" x_train:", x_train.drop(columns=['date']))
    print(" x_test:", x_test.drop(columns=['date']))
    print(" y_train:", y_train)
    print(" y_test:", y_test)
    x_train_features = x_train.drop(columns=['date'])
    feature_columns = list(x_train_features.columns)
    return x_train, x_test, y_train, y_test, feature_columns


def train_model(x_train, y_train):
    x_train = x_train.drop(columns=['date'])
    model = XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )
    model.fit(x_train, y_train)
    return model


def evaluate_model(model, x_test, y_test, model_dir):
    x_test_features = x_test.drop(columns=['date'])
    y_pred = model.predict(x_test_features)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    print(f" Test RMSE: {rmse:.3f}")
    print("Plotting the data")
    df = y_test
    df['predicted_pm25'] = y_pred
    df['date'] = x_test['date']
    df = df.sort_values(by=['date'])
    images_dir = model_dir + "/images"
    if not os.path.exists(images_dir):
        os.mkdir(images_dir)
    file_path = images_dir + "/pm25_hindcast_locally.png"
    plt = plot_air_quality_forecast("wales", "ardiff-newport-road", df, file_path, hindcast=True)
    #plt.show()
    plot_importance(model)
    feature_importance_path = images_dir + "/feature_importance_locally.png"
    plt.savefig(feature_importance_path)
    #plt.show()
    return rmse


def register_model(project, fv, model, rmse, feature_columns, model_dir):
    mr = project.get_model_registry()
    feature_cols_path = os.path.join(model_dir, "feature_columns.json")
    with open(feature_cols_path, "w") as f:
        json.dump(feature_columns, f)
    aq_model = mr.python.create_model(
        name="air_quality_xgboost_model",
        metrics= {
            "RMSE": str(rmse),
        },
        feature_view=fv,
        description="Air Quality (PM2.5) predictor",
    )
    aq_model.save(model_dir)


def main():
    project = get_hopsworks_project()
    fs = project.get_feature_store()

    fview = create_or_get_feature_view(fs)
    x_train, x_test, y_train, y_test, feature_columns = get_train_test_data(fview)
    model = train_model(x_train, y_train)

    model_dir = "air_quality_model_locally"
    if not os.path.exists(model_dir):
        os.mkdir(model_dir)
    model.save_model(model_dir + "/model.json")

    rmse = evaluate_model(model, x_test, y_test, model_dir)
    register_model(project, fview, model, rmse, feature_columns, model_dir)


if __name__ == "__main__":
    main()
