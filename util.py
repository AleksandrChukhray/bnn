from PIL import Image, ImageDraw
from skimage import measure
import StringIO
import data
import numpy as np
import tensorflow as tf

def xys_to_bitmap(xys, height, width, rescale=1.0):
  # note: include trailing 1 dim to easier match model output
  bitmap = np.zeros((int(height*rescale), int(width*rescale), 1), dtype=np.float32)
  for x, y in xys:
    bitmap[int(y*rescale), int(x*rescale), 0] = 1.0  # recall images are (height, width)
  return bitmap

def debug_img(i, bm, o):
  # create a debug image with three columns; 1) original RGB. 2) black/white
  # bitmap of labels 3) black/white bitmap of predictions
  _bs, h, w, _c = bm.shape
  canvas = Image.new('RGB', (w*3, h), (50, 50, 50))
  i = Image.fromarray(i[0])
  i = i.resize((w, h))  
  canvas.paste(i, (0, 0))
  bm = bitmap_to_pil_image(bm[0])
  canvas.paste(bm, (w, 0))
  o = bitmap_to_pil_image(o[0])
  canvas.paste(o, (w*2, 0))
  draw = ImageDraw.Draw(canvas)
  draw.line([w,0,w,h], fill='blue')
  draw.line([2*w,0,2*w,h], fill='blue')
  draw.line([3*w,0,3*w,h], fill='blue')
  return canvas

def explicit_loss_summary(xent_loss, dice_loss):
  return tf.Summary(value=[
    tf.Summary.Value(tag="xent_loss", simple_value=xent_loss),
    tf.Summary.Value(tag="dice_loss", simple_value=dice_loss)
  ])

def pil_image_to_tf_summary(img):
  # serialise png bytes
  sio = StringIO.StringIO()
  img.save(sio, format="png")
  png_bytes = sio.getvalue()
  
  # https://github.com/tensorflow/tensorflow/blob/master/tensorflow/core/framework/summary.proto
  return tf.Summary(value=[tf.Summary.Value(tag="debug_img",
                                            image=tf.Summary.Image(height=img.size[0],
                                                                   width=img.size[1],
                                                                   colorspace=3, # RGB
                                                                   encoded_image_string=png_bytes))])
      
def dice_loss(y, y_hat, batch_size, smoothing=0):
  y = tf.reshape(y, (batch_size, -1))
  y_hat = tf.reshape(y_hat, (batch_size, -1))
  intersection = y * y_hat
  intersection_rs = tf.reduce_sum(intersection, axis=1)
  nom = intersection_rs + smoothing
  denom = tf.reduce_sum(y, axis=1) + tf.reduce_sum(y_hat, axis=1) + smoothing
  score = 2.0 * (nom / denom)
  loss = 1.0 - score
#  loss = tf.Print(loss, [intersection, intersection_rs, nom, denom], first_n=100, summarize=10000)
  return loss

def centroids_of_connected_components(bitmap, threshold=0.05, rescale=1.0):
  # threshold
  mask = bitmap > threshold
  bitmap = np.zeros_like(bitmap)
  bitmap[mask] = 1.0
  # calc connected components
  all_labels = measure.label(bitmap)
  num_components = np.max(all_labels) + 1
  # return centroids
  centroids = []
  for region in measure.regionprops(all_labels):
    cx, cy = map(lambda p: int(p*rescale), region.centroid)
    centroids.append((cx, cy))
  return centroids

def bitmap_from_centroids(centroids, h, w):
  bitmap = np.zeros((h, w, 1))
  for cx, cy in centroids:
    bitmap[cx, cy] = 1.0
  return bitmap

def bitmap_to_pil_image(bitmap):
  h, w, c = bitmap.shape
  assert c == 1
  rgb_array = np.zeros((h, w, 3), dtype=np.uint8)
  single_channel = bitmap[:,:,0] * 255
  rgb_array[:,:,0] = single_channel
  rgb_array[:,:,1] = single_channel
  rgb_array[:,:,2] = single_channel
  return Image.fromarray(rgb_array)

def side_by_side(rgb, bitmap):
  h, w, _ = rgb.shape
  canvas = Image.new('RGB', (w*2, h), (50, 50, 50))
  # paste RGB on left hand side
  lhs = Image.fromarray(rgb)
  canvas.paste(lhs, (0, 0))
  # paste bitmap version of labels on right hand side
  # black with white dots at labels
  rhs = bitmap_to_pil_image(bitmap)
  rhs = rhs.resize((w, h))
  canvas.paste(rhs, (w, 0))
  # draw on a blue border (and blue middle divider) to make it
  # easier to see relative positions.
  draw = ImageDraw.Draw(canvas)
  draw.polygon([0,0,w*2-1,0,w*2-1,h-1,0,h-1], outline='blue')
  draw.line([w,0,w,h], fill='blue')
  return canvas
