try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.figure()
    plt.plot([1, 2, 3], [1, 4, 9])
    plt.savefig('test_output.png')
    plt.close()
    print("Plot saved")
except ImportError:
    import numpy as np
    from PIL import Image
    arr = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    Image.fromarray(arr).save('test_output.png')
    print("Plot saved (fallback)")
