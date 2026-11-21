/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02528(unsigned int count)
{
    const unsigned int limit = 156u;
    return count > limit ? limit : count;
}
