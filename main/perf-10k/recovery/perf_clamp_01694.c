/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01694(unsigned int count)
{
    const unsigned int limit = 171u;
    return count > limit ? limit : count;
}
