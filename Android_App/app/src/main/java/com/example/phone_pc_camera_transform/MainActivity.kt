package com.example.phone_pc_camera_transform

import android.Manifest
import android.app.PictureInPictureParams
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.media.*
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.util.Rational
import android.util.Size
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.io.ByteArrayOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.net.Inet4Address
import java.net.NetworkInterface
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class MainActivity : ComponentActivity() {

    private lateinit var cameraExecutor: ExecutorService
    private var imageAnalysis: ImageAnalysis? = null
    private var cameraProvider: ProcessCameraProvider? = null
    private var camera: Camera? = null
    private var lensFacing = CameraSelector.LENS_FACING_BACK

    // 端口定义
    private val VIDEO_PORT = 6677
    private val AUDIO_PORT = 6678
    private val PC_AUDIO_PORT = 6679

    private var videoServerSocket: ServerSocket? = null
    private var videoClientSocket: Socket? = null
    private var videoOutputStream: DataOutputStream? = null

    private var isAudioRunning = false
    private var isPCAudioRunning = false

    @Volatile
    private var isStreaming = false
    private var isFlashOn = false

    private lateinit var ipTextView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val rootLayout = FrameLayout(this)
        setContentView(rootLayout)

        ipTextView = TextView(this).apply {
            text = "正在获取 IP..."
            textSize = 24f
            setTextColor(Color.GREEN)
            setShadowLayer(5f, 2f, 2f, Color.BLACK)
            layoutParams = FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply {
                gravity = Gravity.CENTER_HORIZONTAL or Gravity.TOP
                topMargin = 100
            }
        }
        rootLayout.addView(ipTextView)

        val ip = getIpAddress()
        ipTextView.text = "本机 IP: $ip\n端口: 6677/6678/6679"

        cameraExecutor = Executors.newSingleThreadExecutor()

        val permissions = arrayOf(Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO)
        if (allPermissionsGranted()) {
            startServices()
        } else {
            requestPermissions.launch(permissions)
        }
    }

    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val aspectRatio = Rational(3, 4)
            val params = PictureInPictureParams.Builder().setAspectRatio(aspectRatio).build()
            enterPictureInPictureMode(params)
        }
    }

    override fun onPictureInPictureModeChanged(isInPictureInPictureMode: Boolean, newConfig: Configuration) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        ipTextView.visibility = if (isInPictureInPictureMode) View.GONE else View.VISIBLE
    }

    private fun getIpAddress(): String {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val networkInterface = interfaces.nextElement()
                val addresses = networkInterface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val address = addresses.nextElement()
                    if (!address.isLoopbackAddress && address is Inet4Address) {
                        return address.hostAddress ?: "未知"
                    }
                }
            }
        } catch (e: Exception) { e.printStackTrace() }
        return "请连接 Wi-Fi"
    }

    private val requestPermissions = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { results ->
        if (results.all { it.value }) startServices()
    }

    private fun allPermissionsGranted() =
        ContextCompat.checkSelfPermission(baseContext, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED &&
                ContextCompat.checkSelfPermission(baseContext, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    private fun startServices() {
        startVideoServer()
        startAudioServer()
        startPCAudioServer()
        startCamera()
    }

    // 1. 视频发送
    private fun startVideoServer() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                videoServerSocket = ServerSocket(VIDEO_PORT)
                while (true) {
                    val socket = videoServerSocket?.accept() ?: break
                    try { videoClientSocket?.close() } catch (e: Exception) {}
                    videoClientSocket = socket
                    videoOutputStream = DataOutputStream(socket.getOutputStream())
                    isStreaming = true
                    listenForCommands(socket)
                }
            } catch (e: Exception) { e.printStackTrace() }
        }
    }

    // 2. 手机麦克风发送
    private fun startAudioServer() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val audioServerSocket = ServerSocket(AUDIO_PORT)
                while (true) {
                    val socket = audioServerSocket.accept()
                    isAudioRunning = true
                    Thread { streamAudio(socket) }.start()
                }
            } catch (e: Exception) { e.printStackTrace() }
        }
    }

    private fun streamAudio(socket: Socket) {
        val sampleRate = 44100
        val channelConfig = AudioFormat.CHANNEL_IN_MONO
        val audioFormat = AudioFormat.ENCODING_PCM_16BIT
        val minBufSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)

        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return

        val recorder = AudioRecord(MediaRecorder.AudioSource.MIC, sampleRate, channelConfig, audioFormat, minBufSize)
        val buffer = ByteArray(minBufSize)
        val output = socket.getOutputStream()

        try {
            recorder.startRecording()
            while (isAudioRunning && socket.isConnected) {
                val read = recorder.read(buffer, 0, buffer.size)
                if (read > 0) output.write(buffer, 0, read)
            }
        } catch (e: Exception) { e.printStackTrace() } finally {
            try { recorder.stop() } catch (e: Exception) {}
            recorder.release()
            socket.close()
        }
    }

    // 3. 接收电脑声音并播放
    private fun startPCAudioServer() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val pcAudioServerSocket = ServerSocket(PC_AUDIO_PORT)
                while (true) {
                    val socket = pcAudioServerSocket.accept()
                    isPCAudioRunning = true
                    Thread { receivePCAudio(socket) }.start()
                }
            } catch (e: Exception) { e.printStackTrace() }
        }
    }

    private fun receivePCAudio(socket: Socket) {
        val sampleRate = 44100
        val channelConfig = AudioFormat.CHANNEL_OUT_MONO
        val audioFormat = AudioFormat.ENCODING_PCM_16BIT
        val minBufSize = AudioTrack.getMinBufferSize(sampleRate, channelConfig, audioFormat)

        val audioTrack = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build())
            .setAudioFormat(AudioFormat.Builder()
                .setEncoding(audioFormat)
                .setSampleRate(sampleRate)
                .setChannelMask(channelConfig)
                .build())
            .setBufferSizeInBytes(minBufSize)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()

        val buffer = ByteArray(minBufSize)
        val input = socket.getInputStream()

        try {
            audioTrack.play()
            while (isPCAudioRunning && socket.isConnected) {
                val read = input.read(buffer)
                if (read > 0) {
                    audioTrack.write(buffer, 0, read)
                } else {
                    break
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        } finally {
            try { audioTrack.stop() } catch (e: Exception) {}
            audioTrack.release()
            socket.close()
        }
    }

    private fun listenForCommands(socket: Socket) {
        Thread {
            try {
                val input = DataInputStream(socket.getInputStream())
                while (socket.isConnected && !socket.isClosed) {
                    val length = input.readUnsignedShort()
                    val buffer = ByteArray(length)
                    input.readFully(buffer)
                    val command = String(buffer, Charsets.UTF_8)

                    runOnUiThread {
                        // 解析 ZOOM 指令
                        if (command == "SWITCH_CAMERA") {
                            switchCamera()
                        } else if (command == "TOGGLE_FLASH") {
                            toggleFlash()
                        } else if (command.startsWith("ZOOM:")) {
                            // 格式: ZOOM:0.5
                            try {
                                val zoomValue = command.split(":")[1].toFloat()
                                setZoom(zoomValue)
                            } catch (e: Exception) {
                                e.printStackTrace()
                            }
                        }
                    }
                }
            } catch (e: Exception) { isStreaming = false }
        }.start()
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            cameraProvider = cameraProviderFuture.get()
            bindCameraUseCases()
        }, ContextCompat.getMainExecutor(this))
    }

    private fun bindCameraUseCases() {
        val cameraProvider = cameraProvider ?: return
        val cameraSelector = CameraSelector.Builder().requireLensFacing(lensFacing).build()

        val resolutionSelector = ResolutionSelector.Builder()
            .setResolutionStrategy(ResolutionStrategy(Size(640, 480), ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER))
            .build()

        imageAnalysis = ImageAnalysis.Builder()
            .setResolutionSelector(resolutionSelector)
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
            .build()

        imageAnalysis?.setAnalyzer(cameraExecutor) { image ->
            try {
                if (isStreaming && videoOutputStream != null) {
                    sendImageToPC(image)
                }
            } catch (e: Exception) { e.printStackTrace() } finally { image.close() }
        }

        try {
            cameraProvider.unbindAll()
            camera = cameraProvider.bindToLifecycle(this, cameraSelector, imageAnalysis)
        } catch (exc: Exception) { Log.e("Camera", "Binding failed", exc) }
    }

    private fun sendImageToPC(image: ImageProxy) {
        val yBuffer = image.planes[0].buffer
        val uBuffer = image.planes[1].buffer
        val vBuffer = image.planes[2].buffer
        val ySize = yBuffer.remaining()
        val uSize = uBuffer.remaining()
        val vSize = vBuffer.remaining()
        val nv21 = ByteArray(ySize + uSize + vSize)

        yBuffer.get(nv21, 0, ySize)
        vBuffer.get(nv21, ySize, vSize)
        uBuffer.get(nv21, ySize + vSize, uSize)

        val yuvImage = YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
        val out = ByteArrayOutputStream()
        yuvImage.compressToJpeg(Rect(0, 0, image.width, image.height), 50, out)
        val imageBytes = out.toByteArray()

        synchronized(videoOutputStream!!) {
            videoOutputStream?.writeByte(0xBE)
            videoOutputStream?.writeByte(0xEF)
            videoOutputStream?.writeInt(imageBytes.size)
            videoOutputStream?.write(imageBytes)
            videoOutputStream?.flush()
        }
    }

    private fun switchCamera() {
        lensFacing = if (lensFacing == CameraSelector.LENS_FACING_FRONT) {
            CameraSelector.LENS_FACING_BACK
        } else {
            CameraSelector.LENS_FACING_FRONT
        }
        bindCameraUseCases()
    }

    private fun toggleFlash() {
        if (camera != null && camera!!.cameraInfo.hasFlashUnit()) {
            isFlashOn = !isFlashOn
            camera!!.cameraControl.enableTorch(isFlashOn)
        }
    }

    // 设置变焦方法
    private fun setZoom(zoomValue: Float) {
        camera?.cameraControl?.setLinearZoom(zoomValue)
    }

    override fun onDestroy() {
        super.onDestroy()
        isAudioRunning = false
        isPCAudioRunning = false
        cameraExecutor.shutdown()
        videoServerSocket?.close()
    }
}