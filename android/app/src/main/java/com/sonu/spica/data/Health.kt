package com.sonu.spica.data

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.ActiveCaloriesBurnedRecord
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import com.sonu.spica.lib.Day
import java.time.Duration
import java.time.LocalDate
import java.time.ZoneId

/** Whether the phone's Health Connect can be read: not there, there but not allowed, or allowed. */
enum class HealthAccess { Unavailable, NotGranted, Granted }

/** One exercise session as Health Connect records it — a run, a ride — in words and minutes. */
data class HealthSession(val kind: String, val minutes: Long, val date: String)

/** Today's steps and active calories, and this week's sessions. Null is not recorded, never 0. */
data class ActivityDay(val steps: Long?, val activeKcal: Double?, val week: List<HealthSession>)

/**
 * Health Connect, read on the phone and nowhere else: steps and active
 * calories for today, exercise sessions for the calendar week. Nothing is
 * written, and nothing goes to the server — Home reads it the way a watch app
 * would.
 */
object Health {
    val PERMISSIONS = setOf(
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(ActiveCaloriesBurnedRecord::class),
        HealthPermission.getReadPermission(ExerciseSessionRecord::class),
    )

    suspend fun access(context: Context): HealthAccess {
        if (HealthConnectClient.getSdkStatus(context) != HealthConnectClient.SDK_AVAILABLE) return HealthAccess.Unavailable
        val granted = HealthConnectClient.getOrCreate(context).permissionController.getGrantedPermissions()
        return if (granted.containsAll(PERMISSIONS)) HealthAccess.Granted else HealthAccess.NotGranted
    }

    suspend fun read(context: Context, todayIso: String): ActivityDay {
        val client = HealthConnectClient.getOrCreate(context)
        val zone = ZoneId.systemDefault()
        val today = LocalDate.parse(todayIso)
        val start = today.atStartOfDay(zone).toInstant()
        val end = today.plusDays(1).atStartOfDay(zone).toInstant()
        val totals = client.aggregate(
            AggregateRequest(
                metrics = setOf(StepsRecord.COUNT_TOTAL, ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL),
                timeRangeFilter = TimeRangeFilter.between(start, end),
            ),
        )
        val monday = today.minusDays(Day.weekIndex(todayIso).toLong()).atStartOfDay(zone).toInstant()
        val sessions = client.readRecords(
            ReadRecordsRequest(ExerciseSessionRecord::class, TimeRangeFilter.between(monday, end)),
        ).records.map {
            HealthSession(
                kind = kindOf(it.exerciseType, it.title),
                minutes = Duration.between(it.startTime, it.endTime).toMinutes(),
                date = it.startTime.atZone(zone).toLocalDate().toString(),
            )
        }
        return ActivityDay(
            steps = totals[StepsRecord.COUNT_TOTAL],
            activeKcal = totals[ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL]?.inKilocalories,
            week = sessions,
        )
    }

    /** The session in a word; anything the app has no word for is a workout, or the title it was given. */
    private fun kindOf(type: Int, title: String?): String = when (type) {
        ExerciseSessionRecord.EXERCISE_TYPE_RUNNING, ExerciseSessionRecord.EXERCISE_TYPE_RUNNING_TREADMILL -> "Running"
        ExerciseSessionRecord.EXERCISE_TYPE_BIKING, ExerciseSessionRecord.EXERCISE_TYPE_BIKING_STATIONARY -> "Cycling"
        ExerciseSessionRecord.EXERCISE_TYPE_WALKING -> "Walking"
        ExerciseSessionRecord.EXERCISE_TYPE_HIKING -> "Hiking"
        ExerciseSessionRecord.EXERCISE_TYPE_SWIMMING_POOL, ExerciseSessionRecord.EXERCISE_TYPE_SWIMMING_OPEN_WATER -> "Swimming"
        ExerciseSessionRecord.EXERCISE_TYPE_STRENGTH_TRAINING, ExerciseSessionRecord.EXERCISE_TYPE_WEIGHTLIFTING -> "Strength"
        ExerciseSessionRecord.EXERCISE_TYPE_YOGA -> "Yoga"
        else -> title?.takeIf { it.isNotBlank() } ?: "Workout"
    }
}
