/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07484(unsigned int count)
{
    const unsigned int limit = 246u;
    return count > limit ? limit : count;
}
