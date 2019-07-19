'''
Author: Xingtong Liu, Ayushi Sinha, Masaru Ishii, Gregory D. Hager, Austin Reiter, Russell H. Taylor, and Mathias Unberath

Copyright (C) 2019 Johns Hopkins University - All Rights Reserved
You may use, distribute and modify this code under the
terms of the GNU GENERAL PUBLIC LICENSE Version 3 license for non-commercial usage.

You should have received a copy of the GNU GENERAL PUBLIC LICENSE Version 3 license with
this file. If not, please write to: xliu89@jh.edu or rht@jhu.edu or unberath@jhu.edu
'''

import torch
from torch import nn


# Use scale invariant loss for student learning from teacher
class ScaleInvariantLoss(nn.Module):
    def __init__(self, epsilon=1.0e-8):
        super(ScaleInvariantLoss, self).__init__()
        self.epsilon = torch.tensor(epsilon).float().cuda()

    def forward(self, x):
        predicted_depths, goal_depths, boundaries = x
        depth_ratio_map = torch.log(boundaries * predicted_depths + self.epsilon) - \
                          torch.log(boundaries * goal_depths + self.epsilon)

        weighted_sum = torch.sum(boundaries, dim=(1, 2, 3))
        loss_1 = torch.sum(depth_ratio_map * depth_ratio_map,
                           dim=(1, 2, 3)) / weighted_sum
        sum_2 = torch.sum(depth_ratio_map, dim=(1, 2, 3))
        loss_2 = (sum_2 * sum_2) / (weighted_sum * weighted_sum)
        return torch.mean(loss_1 + loss_2)


class NormalizedWeightedMaskedL2Loss(nn.Module):
    def __init__(self, epsilon=1.0):
        super(NormalizedWeightedMaskedL2Loss, self).__init__()
        self.epsilon = torch.tensor(epsilon).float().cuda()

    def forward(self, x):
        depth_maps, warped_depth_maps, intersect_masks, translations = x
        # loss = torch.sum(torch.log(1.0 + torch.abs(intersect_masks * (depth_maps - warped_depth_maps))), dim=(1, 2, 3)) / (self.epsilon + torch.sum(intersect_masks, dim=(1, 2, 3)))

        translations = translations.view(-1, 3, 1)
        translation_norms = torch.sqrt(torch.sum(translations * translations, dim=(1, 2))).view(-1)
        translation_weights = (
                torch.tensor(1.0).float().cuda() / (torch.tensor(1.0e-8).float().cuda() + translation_norms)).view(
            -1)
        loss = torch.sum(intersect_masks * (depth_maps - warped_depth_maps) * (depth_maps - warped_depth_maps),
                         dim=(1, 2, 3), keepdim=False) / (0.5 * torch.sum(
            intersect_masks * (depth_maps * depth_maps + warped_depth_maps * warped_depth_maps), dim=(1, 2, 3),
            keepdim=False) + self.epsilon)
        loss = torch.sum(loss * translation_weights) / torch.sum(translation_weights)
        return loss


class SparseMaskedL1Loss(nn.Module):
    def __init__(self, epsilon=1.0):
        super(SparseMaskedL1Loss, self).__init__()
        self.epsilon = torch.tensor(epsilon).float().cuda()

    def forward(self, x):
        flows, flows_from_depth, sparse_masks = x
        loss = torch.sum(sparse_masks * torch.abs(flows - flows_from_depth),
                         dim=(1, 2, 3)) / (self.epsilon + torch.sum(sparse_masks, dim=(1, 2, 3)))
        return torch.mean(loss)


class SparseMaskedL1LossDisplay(nn.Module):
    def __init__(self, epsilon=1.0):
        super(SparseMaskedL1LossDisplay, self).__init__()
        self.epsilon = torch.tensor(epsilon).float().cuda()

    def forward(self, x):
        flows, flows_from_depth, sparse_masks = x
        loss = torch.sum(sparse_masks * torch.abs(flows - flows_from_depth),
                         dim=(1, 2, 3), keepdim=False) / (
                       self.epsilon + torch.sum(sparse_masks, dim=(1, 2, 3), keepdim=False))
        return loss


class MaskedL1Loss(nn.Module):
    def __init__(self, epsilon=1.0):
        super(MaskedL1Loss, self).__init__()
        self.epsilon = torch.tensor(epsilon).float().cuda()

    def forward(self, x):
        images, twice_warped_images, intersect_masks = x
        loss = torch.sum(intersect_masks * torch.abs(images - twice_warped_images), dim=(1, 2, 3)) / (
                self.epsilon + torch.sum(intersect_masks, dim=(1, 2, 3)))
        return torch.mean(loss)


class NormalizedL2Loss(nn.Module):
    def __init__(self, eps=1.0e-3):
        super(NormalizedL2Loss, self).__init__()
        self.eps = eps

    def forward(self, x):
        depth_maps, warped_depth_maps, intersect_masks = x

        mean_value = torch.sum(intersect_masks * depth_maps, dim=(1, 2, 3), keepdim=False) / (
                self.eps + torch.sum(intersect_masks, dim=(1, 2, 3),
                                     keepdim=False))
        loss = torch.sum(intersect_masks * (depth_maps - warped_depth_maps) * (depth_maps - warped_depth_maps),
                         dim=(1, 2, 3), keepdim=False) / (0.5 * torch.sum(
            intersect_masks * (depth_maps * depth_maps + warped_depth_maps * warped_depth_maps), dim=(1, 2, 3),
            keepdim=False) + 1.0e-5 * mean_value * mean_value)
        return torch.mean(loss)


class NormalizedL1Loss(nn.Module):
    def __init__(self, eps=1.0e-3):
        super(NormalizedL1Loss, self).__init__()
        self.eps = eps

    def forward(self, x):
        depth_maps, warped_depth_maps, masks = x

        mean_value = torch.sum(masks * depth_maps, dim=(1, 2, 3), keepdim=False) / (
                self.eps + torch.sum(masks, dim=(1, 2, 3),
                                     keepdim=False))
        loss = torch.sum(masks * torch.abs(depth_maps - warped_depth_maps),
                         dim=(1, 2, 3), keepdim=False) / (0.5 * torch.sum(
            masks * (torch.abs(depth_maps) + torch.abs(warped_depth_maps)), dim=(1, 2, 3),
            keepdim=False) + 1.0e-5 * mean_value)
        return torch.mean(loss)


class MaskedScaleInvariantLoss(nn.Module):
    def __init__(self, epsilon=1.0e-8):
        super(MaskedScaleInvariantLoss, self).__init__()
        self.epsilon = torch.tensor(epsilon).float().cuda()
        self.zero = torch.tensor(0.0).float().cuda()

    def forward(self, x):
        absolute_depth_estimations, input_sparse_depths, input_sparse_masks = x

        depth_ratio_map = torch.where(input_sparse_depths < 0.5, self.zero,
                                      torch.log(absolute_depth_estimations + self.epsilon) -
                                      torch.log(input_sparse_depths))

        weighted_sum = torch.sum(input_sparse_masks, dim=(1, 2, 3))
        loss_1 = torch.sum(torch.mul(input_sparse_masks, depth_ratio_map * depth_ratio_map),
                           dim=(1, 2, 3)) / weighted_sum
        sum_2 = torch.sum(torch.mul(input_sparse_masks, depth_ratio_map), dim=(1, 2, 3))
        loss_2 = (sum_2 * sum_2) / (weighted_sum * weighted_sum)

        return torch.mean(loss_1 + loss_2)
