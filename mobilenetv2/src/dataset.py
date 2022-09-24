# Copyright 2020 
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""Create train or eval dataset."""
import os
import mindspore.common.dtype as mstype
import mindspore.dataset.engine as de
import mindspore.dataset.vision.c_transforms as C
import mindspore.dataset.transforms.c_transforms as C2


def create_dataset(dataset_path, do_train, config, repeat_num=1):
    """
    Create a train or eval dataset.

    Args:
        dataset_path (string): The path of dataset.
        do_train (bool): Whether dataset is used for train or eval.
        config: configuration
        repeat_num (int): The repeat times of dataset. Default: 1.
    Returns:
        Dataset.
    """
    if do_train:
        dataset_path = os.path.join(dataset_path, 'train')
        do_shuffle = True
    else:
        dataset_path = os.path.join(dataset_path, 'eval')
        do_shuffle = False

    device_id = 0
    device_num = 1
    if config.platform == "GPU":
        if config.run_distribute:
            from mindspore.communication.management import get_rank, get_group_size
            device_id = get_rank()
            device_num = get_group_size()
    elif config.platform == "Ascend":
        device_id = int(os.getenv('DEVICE_ID'))
        device_num = int(os.getenv('RANK_SIZE'))

    if device_num == 1 or not do_train:
        ds = de.Cifar10Dataset(dataset_path, num_parallel_workers=4, shuffle=do_shuffle)
    else:
        ds = de.Cifar10Dataset(dataset_path, num_parallel_workers=4, shuffle=do_shuffle,
                               num_shards=device_num, shard_id=device_id)

    resize_height = config.image_height
    resize_width = config.image_width
    buffer_size = 100
    rescale = 1.0 / 255.0
    shift = 0.0

    # define map operations
    random_crop_op = C.RandomCrop((32, 32), (4, 4, 4, 4))
    random_horizontal_flip_op = C.RandomHorizontalFlip(device_id / (device_id + 1))

    resize_op = C.Resize((resize_height, resize_width))
    rescale_op = C.Rescale(rescale, shift)
    normalize_op = C.Normalize([0.4914, 0.4822, 0.4465], [0.2023, 0.1994, 0.2010])

    change_swap_op = C.HWC2CHW()

    trans = []
    if do_train:
        trans += [random_crop_op, random_horizontal_flip_op]

    trans += [resize_op, rescale_op, normalize_op, change_swap_op]

    type_cast_op = C2.TypeCast(mstype.int32)

    ds = ds.map(input_columns="label", operations=type_cast_op)
    ds = ds.map(input_columns="image", operations=trans)

    # apply shuffle operations
    ds = ds.shuffle(buffer_size=buffer_size)

    # apply batch operations
    ds = ds.batch(config.batch_size, drop_remainder=True)

    # apply dataset repeat operation
    ds = ds.repeat(repeat_num)

    return ds
