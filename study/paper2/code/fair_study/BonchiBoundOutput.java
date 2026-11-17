import java.lang.reflect.Method;


public final class BonchiBoundOutput {
    public static void main(String[] args) throws Exception {
        Class<?> solver = Class.forName("KEtaCores_DynamicProgramming_BigDecimals_IncrementalInitialEtaDegrees_LB");
        Method run = solver.getDeclaredMethod("run", String.class, double.class, String.class);
        run.setAccessible(true);
        run.invoke(null, args[0], Double.parseDouble(args[1]), Long.toString(System.currentTimeMillis()));
    }
}
