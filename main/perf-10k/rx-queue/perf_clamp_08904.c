/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08904(unsigned int count)
{
    const unsigned int limit = 233u;
    return count > limit ? limit : count;
}
