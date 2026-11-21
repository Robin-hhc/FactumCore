/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00936(unsigned int count)
{
    const unsigned int limit = 233u;
    return count > limit ? limit : count;
}
