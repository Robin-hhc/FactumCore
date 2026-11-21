/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03009(unsigned int count)
{
    const unsigned int limit = 116u;
    return count > limit ? limit : count;
}
