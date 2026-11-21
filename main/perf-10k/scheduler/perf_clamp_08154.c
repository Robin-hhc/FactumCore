/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08154(unsigned int count)
{
    const unsigned int limit = 182u;
    return count > limit ? limit : count;
}
