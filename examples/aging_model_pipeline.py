"""Aging model pipeline script

This script allows the user to execute an example workflow for designing and evaluating an experiment,
specifically the pi experiment.
Being more precisely, we
* use as statistical model the white Gaussian noise model with
* parametric function the aging_model provided in the parametric function library
* benchmark various experiments against each other and
* plot several metrics
"""

####
# Importing modules

import numpy as np

from src.benchmarking.benchmarking import Benchmarking
from src.oed.experiments import DDesign
from src.oed.experiments import LatinHypercube
from src.oed.experiments import PiDesign
from src.oed.experiments import (
    PointPredictionDesign,
)
from src.oed.experiments import Random

####
# Designs
from src.oed.metrics.metric_library import (
    DeterminantOfFisherInformationMatrix,
)
from src.oed.metrics.metric_library.estimation_mean_error import EstimationMeanError
from src.oed.metrics.metric_library import (
    EstimationMeanParameterEstimations,
)
from src.oed.metrics.metric_library import KFoldCrossValidation
from src.oed.metrics.metric_library import StdParameterEstimations
from src.minimizer.minimizer_library.differential_evolution import DifferentialEvolution
from src.parametric_function_library.aging_model import AgingModel
from oed.statistical_models.statistical_model_library import (
    GaussianNoiseModel,
)

#################################
#################################
# SETUP

####
# statistical model
from src.uncertainty_quantification.parametric_function_with_uncertainty import (
    ParametricFunctionWithUncertainty,
)
from src.uncertainty_quantification.probability_measures.multivariate_gaussian import (
    MultivariateGaussian,
)

theta = np.array([1.8, 402, 0.13])

number_designs = 5
number_of_evaluations = 100

# real noise
sigma = 0.002

#################################
#################################
# Pipeline

####
# bounds
lower_bounds_x = np.array([0.05, 279.15])
upper_bounds_x = np.array([1, 333.15])

lower_bounds_theta = np.array([0.01, 0, 0])
upper_bounds_theta = np.array([10, 10000, 1])

# Setup a parametric function family
parametric_function = AgingModel()

####
# minimizer
minimizer = DifferentialEvolution()

statistical_model = GaussianNoiseModel(
    function=parametric_function,
    lower_bounds_x=lower_bounds_x,
    upper_bounds_x=upper_bounds_x,
    lower_bounds_theta=lower_bounds_theta,
    upper_bounds_theta=upper_bounds_theta,
    sigma=sigma,
)


####
# blackbox function
def blackbox_model(x):
    return statistical_model.random(theta=theta, x=x)


LH = LatinHypercube(
    lower_bounds_design=lower_bounds_x,
    upper_bounds_design=upper_bounds_x,
    number_designs=2 * number_designs,
)

# print(LH.experiment, LH.name)

random_design = Random(
    number_designs=2 * number_designs,
    lower_bounds_design=lower_bounds_x,
    upper_bounds_design=upper_bounds_x,
)

# We split the number of experiment in half and perform first a latin hypercube
LH_half = LatinHypercube(
    lower_bounds_design=lower_bounds_x,
    upper_bounds_design=upper_bounds_x,
    number_designs=number_designs,
)

initial_theta = statistical_model.calculate_maximum_likelihood_estimation(
    x0=LH_half.experiment,
    y=np.array([blackbox_model(x) for x in LH_half.experiment]),
    minimizer=minimizer,
)

# Uncertainty quantification

covariance_matrix = statistical_model.calculate_cramer_rao_lower_bound(
    x0=LH_half.experiment, theta=initial_theta
)

probability_measure_on_parameter_space = MultivariateGaussian(
    mean=initial_theta, covariance_matrix=covariance_matrix
)

parametric_function_with_uncertainty = ParametricFunctionWithUncertainty(
    parametric_function=parametric_function,
    probability_measure_on_parameter_space=probability_measure_on_parameter_space,
    sample_size_parameters=1000,
)

alpha = 0.9
x = LH.experiment[3]
upper_quantile = parametric_function_with_uncertainty.calculate_quantile(
    x=x, alpha=alpha
)

parametric_function_with_uncertainty.histo(x)

print(
    f"the upper quantile at design {x} with estimated outcome {parametric_function(theta=initial_theta,x=x)} is \n {upper_quantile}"
)

new_design = PointPredictionDesign(
    lower_bounds_design=lower_bounds_x,
    upper_bounds_design=upper_bounds_x,
    minimizer=minimizer,
    parametric_function_with_uncertainty=parametric_function_with_uncertainty,
    alpha=0.95,
)


input(new_design.experiment)

min_entry = PiDesign(
    number_designs=number_designs,
    lower_bounds_design=lower_bounds_x,
    upper_bounds_design=upper_bounds_x,
    index=1,
    initial_theta=initial_theta,
    previous_experiment=LH_half,
    statistical_model=statistical_model,
    minimizer=minimizer,
)

max_det = DDesign(
    number_designs=number_designs,
    lower_bounds_design=lower_bounds_x,
    upper_bounds_design=upper_bounds_x,
    initial_theta=initial_theta,
    statistical_model=statistical_model,
    minimizer=minimizer,
    previous_experiment=LH_half,
)

metrics = [
    DeterminantOfFisherInformationMatrix(
        theta=initial_theta, statistical_model=statistical_model
    ),
    EstimationMeanParameterEstimations(),
    StdParameterEstimations(),
    EstimationMeanError(
        number_evaluations=1000, theta=theta, statistical_model=statistical_model
    ),
    KFoldCrossValidation(
        statistical_model=statistical_model, minimizer=minimizer, number_splits=2
    ),
]

####
# benchmarking


benchmarking = Benchmarking(
    blackbox_model=blackbox_model,
    statistical_model=statistical_model,
    experiments=[LH, random_design, min_entry, max_det],
)

benchmarking.evaluate_experiments(
    number_of_evaluations=number_of_evaluations, minimizer=minimizer
)

# Save results to csv
benchmarking.save_to_csv()

k_fold_data = {}
for design in benchmarking.evaluations_blackbox_function.keys():
    k_fold_data[design] = benchmarking.evaluations_blackbox_function[design][0]

#####
# saving the benchmarking results


#####
# plotting

baseline = np.sqrt(
    np.array(
        [
            statistical_model.calculate_cramer_rao_lower_bound(
                x0=design.experiment, theta=theta
            ).diagonal()
            for design in benchmarking.experiments
        ]
    ).T
)

fig2 = metrics[2].plot(
    evaluations_blackbox_function_for_each_experiment=benchmarking.evaluations_blackbox_function,
    estimations_of_parameter_for_each_experiment=benchmarking.maximum_likelihood_estimations,
    baseline=baseline,
)
fig2.show()

fig0 = metrics[0].plot(
    evaluations_blackbox_function_for_each_experiment=benchmarking.evaluations_blackbox_function,
    estimations_of_parameter_for_each_experiment=benchmarking.maximum_likelihood_estimations,
    baseline="max",
)
fig0.show()

fig1 = metrics[1].plot(
    evaluations_blackbox_function_for_each_experiment=benchmarking.evaluations_blackbox_function,
    estimations_of_parameter_for_each_experiment=benchmarking.maximum_likelihood_estimations,
    baseline=theta,
)
fig1.show()

fig3 = metrics[3].plot(
    evaluations_blackbox_function_for_each_experiment=benchmarking.evaluations_blackbox_function,
    estimations_of_parameter_for_each_experiment=benchmarking.maximum_likelihood_estimations,
    baseline="min",
)
fig3.show()

fig4 = metrics[4].plot(
    evaluations_blackbox_function_for_each_experiment=k_fold_data, baseline="min"
)
fig4.show()

fig = benchmarking.plot_estimations()
fig.show()
