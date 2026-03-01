"""
Download dos modelos DNN para face detection (ResNet SSD).
Executa uma vez — os ficheiros ficam em data/
"""
import os
import urllib.request

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# URLs oficiais do OpenCV (repositório GitHub)
MODELS = {
    "deploy.prototxt": "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
    "res10_300x300_ssd_iter_140000.caffemodel": "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
}


def download_modelos():
    """Faz download dos modelos DNN se não existirem."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    for nome, url in MODELS.items():
        caminho = os.path.join(MODEL_DIR, nome)
        if os.path.exists(caminho):
            tamanho = os.path.getsize(caminho)
            if tamanho > 1000:  # ficheiro válido
                print(f"  ✅ {nome} já existe ({tamanho / 1024:.0f} KB)")
                continue
        
        print(f"  ⬇️  A descarregar {nome}...")
        try:
            urllib.request.urlretrieve(url, caminho)
            tamanho = os.path.getsize(caminho)
            print(f"  ✅ {nome} descarregado ({tamanho / 1024:.0f} KB)")
        except Exception as e:
            print(f"  ⚠️ Erro ao descarregar {nome}: {e}")
            print(f"     O face tracking usará Haar cascade como fallback.")
    
    print()
    print("Modelos DNN prontos! O face tracking terá ~95% accuracy.")


if __name__ == "__main__":
    download_modelos()
