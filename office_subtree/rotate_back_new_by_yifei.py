import math


def rotate_back_new(rotated_points, theta, center=(0, 0)):
    """
    将旋转后的点翻转回原始坐标。
    rotated_points: 旋转后的顶点列表。
    theta: 旋转角度（弧度）。
    center: 平移中心点(x, y)。
    rotation_door_position: 旋转后的门位置。
    返回:
        original_points: 原始顶点列表。
        original_points_door: 原始门位置。
    """
    cx, cy = center[0]
    cx1, cy1 = center[1]
    # 逆旋转角度
    cos_t = math.cos(-theta)
    sin_t = math.sin(-theta)

    # 逆旋转
    unrotated_points = []
    for x, y in rotated_points:
        x = x - cx1
        y = y - cy1
        x_unrot = x * cos_t - y * sin_t + cx
        y_unrot = x * sin_t + y * cos_t + cy
        unrotated_points.append((x_unrot, y_unrot))


    return unrotated_points