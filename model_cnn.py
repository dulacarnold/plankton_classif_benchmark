import tensorflow as tf
import tensorflow_hub as hub
import tensorflow_addons as tfa
from tensorflow.keras import layers, optimizers, losses, callbacks 
import tensorflow_addons as tfa
import os
import pickle
import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score
import glob



def create_cnn(fc_layers_nb, fc_layers_dropout, fc_layers_size, classif_layer_dropout, classif_layer_size,  train_fe = False, glimpse = True):

    """
    Generates a CNN model. 
    
    Args:
        fc_layers_nb (int): number of fully connected layers 
        fc_layers_size (int): size of fully connected layers 
        fc_layers_dropout (float): dropout of fully connected layers 
        classif_layer_size (int): size of classification layer (i.e. number of classes to predict)
        classif_layer_dropout (float): dropout of classification layer
        train_fe (bool): whether to train the feature extractor (True) or only classification head (False)
        glimpse(bool): whether to show a model summary
    
    Returns:
        model (tensorflow.python.keras.engine.sequential.Sequential): CNN model
        
    """
    
    ## Initiate empty model
    model = tf.keras.Sequential()
    
    ## MobileNet V2 feature extractor
    fe_url = "https://tfhub.dev/google/tf2-preview/mobilenet_v2/feature_vector/4"
    fe_layer = hub.KerasLayer(fe_url, input_shape=(224, 224, 3))
    # Set feature extractor to trainability
    fe_layer.trainable=train_fe
    model.add(fe_layer)
    
    ## Fully connected layers
    for i in range(fc_layers_nb):
        model.add(layers.Dropout(fc_layers_dropout))
        model.add(layers.Dense(fc_layers_size, activation='relu'))
    
    ### Classification layers
    model.add(layers.Dropout(classif_layer_dropout))
    model.add(layers.Dense(classif_layer_size))
    
    if glimpse:
        model.summary()

    return model

def compile_cnn(model, initial_lr, steps_per_epoch, lr_method='constant', decay_rate=None, loss='cce'):
    """
    Compiles a CNN model. 
    
    Args:
        model (tensorflow.python.keras.engine.sequential.Sequential): CNN model to compile
        lr_method (str): method for learning rate. 'constant' for a constant learning rate, 'decay' for a decay
        initial_lr (float): initial learning rate. If lr_method is 'constant', set learning rate to this value
        steps_per_epochs (int): number of training steps at each epoch. Usually number_of_epochs // batch_size
        decay_rate (float): rate for learning rate decay
        loss (str): method to compute loss. 'cce' for CategoricalCrossentropy (see https://www.tensorflow.org/api_docs/python/tf/keras/losses/CategoricalCrossentropy), 'sfce' for SigmoidFocalCrossEntropy (see https://www.tensorflow.org/addons/api_docs/python/tfa/losses/SigmoidFocalCrossEntropy), usefull for unbalanced classes

    
    Returns:
        model (tensorflow.python.keras.engine.sequential.Sequential): compiled CNN model
        
    """
    # TODO if lr_method='decay', decay_rate in mandatory

    ## Learning rate
    if lr_method == 'decay':
        lr = optimizers.schedules.InverseTimeDecay(
                    initial_lr, steps_per_epoch, decay_rate, staircase=False, name=None
        )
    else: # Keep constant learning rate
        lr = initial_lr
    
    ## Optimizer: use Adam
    optimizer = optimizers.Adam(learning_rate=lr)
    
    
    ## Loss
    if loss == 'cce':
        loss = losses.CategoricalCrossentropy(from_logits=True,reduction=losses.Reduction.SUM_OVER_BATCH_SIZE)
    elif loss == 'sfce':
        loss = tfa.losses.SigmoidFocalCrossEntropy(from_logits=True,reduction=losses.Reduction.SUM_OVER_BATCH_SIZE)
    
    
    model.compile(
      optimizer=optimizer,
      loss=loss,
      metrics='accuracy'
    )
    
    return model


def train_cnn(model, train_batches, valid_batches, batch_size, epochs, class_weights, output_dir):
    """
    Trains a CNN model. 
    
    Args:
        model (tensorflow.python.keras.engine.sequential.Sequential): CNN model to train
        train_batches
        train_batches
        batch_size (int): size if batches
        epochs (int): number of epochs to train for
        class_weight(dict): weights for classes
        output_dir (str): directory where to save model weights

    
    Returns:
        nothing
        
    """
    #TODO add class weights
    # Set callbacks
    filepath = os.path.join(output_dir, "weights.{epoch:02d}.hdf5")
    cp_callback = callbacks.ModelCheckpoint(
        filepath=filepath,
        monitor='val_loss',
        save_best_only=True,
        mode='min',
        save_weights_only=True,
        save_freq='epoch',
        verbose=1)

    # Compute number of steps per epochs     
    steps_per_epoch = len(train_batches)//batch_size
    validation_steps = len(valid_batches)//batch_size
    
    # Fit the model.
    history = model.fit(
        train_batches, 
        epochs=epochs,
        steps_per_epoch=steps_per_epoch,
        validation_data=valid_batches,
        validation_steps=validation_steps,
        callbacks=[cp_callback],
        class_weight=class_weights
    )
    
    # Write training history 
    with open(os.path.join(output_dir, "train_results.pickle"),"wb") as results_file:
        pickle.dump(history.history, results_file)
    
    return history


def predict_evaluate_cnn(model, batches, classes, output_dir):
    """
    Predict batches and evaluate a CNN model by computing accuracy and loss and writting predictions and accuracy into a test file. 
    
    Args:
        model (tensorflow.python.keras.engine.sequential.Sequential): CNN model to eavluate
        batches (datasets.DataGenerator): batches of data to predict
        classes (array): classes to predict
        output_dir (str): directory where to save prediction results

    
    Returns:
        accuracy (float) accuracy value for test data
        loss (float): loss (categorical cross entropy) value for test data
        
    """
    
    # Load last saved weights to CNN model
    saved_weights = glob.glob(os.path.join(output_dir, "*.hdf5"))
    saved_weights.sort()
    model.load_weights(saved_weights[-1])
    
    # Initiate empty lists for predicted and true labels
    predicted_batches = []
    true_batches = []
    
    # Loop over test batches
#    for image_batch, label_batch in batches:
#        # Predict images of batch
#        predicted_batches.extend(model.predict(image_batch))
#        # Extract true labels of batch
#        true_batches.extend(label_batch)
    
    # Loop over test batches
    for i in range(len(batches)+1):
        # Define image batch and label batch
        image_batch = batches[i][0]
        label_batch = batches[i][1]
        
        # if batch is not empty, predict it
        if len(image_batch) > 0:
            # Predict images of batch
            predicted_batches.extend(model.predict(image_batch))
            # Extract true labels of batch
            true_batches.extend(label_batch)
    
    # Convert to class names
    predicted_classes = classes[np.argmax(predicted_batches, axis=1)]
    true_classes = classes[np.argmax(true_batches, axis=1)]
    
    # Compute accuracy and loss from true labels and predicted labels
    accuracy = accuracy_score(true_classes, predicted_classes)
    balanced_accuracy = balanced_accuracy_score(true_classes, predicted_classes)
    cce = losses.CategoricalCrossentropy()
    loss = cce(true_batches, predicted_batches).numpy()
    print(f'Test accuracy = {accuracy}')
    print(f'Balanced test accuracy = {balanced_accuracy}')
    print(f'Test loss = {loss}')
    
    # Write true and predicted classes to test file
    with open(os.path.join(output_dir, 'test_results.pickle'),'wb') as test_file:
        pickle.dump({'true_classes': true_classes,
                     'predicted_classes': predicted_classes,
                     'classes': classes,
                     'accuracy': accuracy,
                     'balanced_accuracy': balanced_accuracy},
                    test_file)
        
    return accuracy, loss