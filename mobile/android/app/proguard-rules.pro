# Room 2.2.5 (transitive through WorkManager 2.7.0) instantiates this
# generated database through Class.newInstance(). Its consumer rules keep
# the class name, but R8 full mode removes the no-argument constructor.
# Keep only that reflective entry point; retain optimization elsewhere.
-keepclassmembers class androidx.work.impl.WorkDatabase_Impl {
    public <init>();
}

# ML Kit discovers these components from Android manifest metadata through
# Firebase's Class.forName(...).getDeclaredConstructor().newInstance().
# R8 full mode retained their names but removed their public constructors;
# SharedPrefManager then resolved to null during InputImage creation.
-keepclassmembers class * implements com.google.firebase.components.ComponentRegistrar {
    public <init>();
}
