"""Lesion segmentation workflow."""
import lesionpypeline.log as logging
import lesionpypeline.config as config
import lesionpypeline.sequences as seq
import lesionpypeline.segmentation as seg

log = logging.get_logger(__name__)

# TODO insert correct names
ADC_ID = 'adc'
DWI_ID = 'dwi'


def resample(sequences):
    """Resample and coregister the given set of sequences."""
    fixed_image_key = config.conf['registration_base']
    if fixed_image_key not in sequences:
        raise ValueError('The configured registration base sequence {} is not'
                         ' availabe in the current case: {}'
                         .format(fixed_image_key, sequences.keys()))
    result = dict(sequences)
    # -- Resampling
    log.info('Resampling...')
    fixed_image = seq.resample(result[fixed_image_key])
    result[fixed_image_key] = fixed_image
    for key in (result.viewkeys()
                - {fixed_image_key, ADC_ID, DWI_ID}):
        result[key], _ = seq.register(result[key], fixed_image)

    # special case: adc is not registered to the fixed image. Instead, the
    # transformation resulting from DWI_ID registration is applied.
    if DWI_ID in result:
        result[DWI_ID], transform = seq.register(result[DWI_ID], fixed_image)
    if ADC_ID in result:
        if transform is not None:
            result[ADC_ID] = transform(result[ADC_ID], transform)
        else:
            result[ADC_ID] = seq.register(result[ADC_ID], fixed_image)
    return result


def skullstrip(sequences):
    """Perform skullstripping and mask sequences accordingly."""
    skullstrip_base_key = config.conf['skullstripping_base']
    if skullstrip_base_key not in sequences:
        raise ValueError('The configured skullstripping base sequence {} is'
                         ' not availabe in the current case: {}'
                         .format(skullstrip_base_key, sequences.keys()))
    result = dict(sequences)
    log.info('Skullstripping...')
    mask = seq.skullstrip(result[skullstrip_base_key])

    for key in result:
        result[key] = seq.apply_mask(result[key], mask)
    return result, mask


def correct_biasfield(sequences, mask):
    """Correct biasfied in given sequences."""
    # -- Biasfield correction
    log.info('Biasfield correction...')
    result = dict(sequences)
    for key in result:
        result[key] = seq.correct_biasfield(result[key], mask)


def standardize_intensityrange(sequences, mask):
    """Standardize intensityrange for given sequences."""
    intensity_models = config.conf['intensity_models']
    for key in sequences:
        if key not in intensity_models:
            raise KeyError('No intensity model for sequence {} configured in'
                           ' classifier pack!'.format(key))

    result = dict(sequences)
    log.info('Intensityrange standardization...')
    for key in result:
        result[key] = seq.standardize_intensityrange(
            result[key], mask, intensity_models[key])
    return result


def segment(sequences, mask):
    """Segment the lesions in the given images."""
    log.info('Extracting features...')
    features = seg.extract_features(sequences, mask)

    log.info('Applying classifier...')
    segmentation_image, probability_image = seg.apply_rdf(features, mask)

    return segmentation_image, probability_image
